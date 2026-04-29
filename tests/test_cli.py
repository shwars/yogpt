import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace

from yogpt import cli


MODEL = {
    "name": "test",
    "model_name": "test-model",
    "api_key": "test-key",
    "base_url": "https://example.com/v1",
}


class FakeResponses:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def create(self, **request):
        self.requests.append(request)
        if request.get("stream"):
            return iter(self.response)
        return self.response


class FakeBinary:
    def __init__(self, data):
        self.data = data

    def write_to_file(self, path):
        with open(path, "wb") as f:
            f.write(self.data)


class FakeContainerContent:
    def __init__(self, data):
        self.data = data
        self.calls = []
        self.fail = False

    def retrieve(self, file_id, *, container_id):
        self.calls.append((container_id, file_id))
        if self.fail:
            raise RuntimeError("container download failed")
        return FakeBinary(self.data)


class FakeContainerFiles:
    def __init__(self, data):
        self.content = FakeContainerContent(data)

    def list(self, container_id):
        return SimpleNamespace(data=[])


class FakeClient:
    def __init__(self, response):
        self.responses = FakeResponses(response)
        self.containers = SimpleNamespace(files=FakeContainerFiles(b"from-container"))
        self.files = SimpleNamespace(content=lambda file_id: FakeBinary(b"from-files"))


class CliUnitTests(unittest.TestCase):
    def test_expand_env_vars_recursively(self):
        config = {
            "api_key": "%api_key%",
            "nested": ["x-%folder_id%", {"model": "gpt://%folder_id%/qwen"}],
        }
        expanded = cli.expand_env_vars(config, {"api_key": "secret", "folder_id": "folder"})
        self.assertEqual(expanded["api_key"], "secret")
        self.assertEqual(expanded["nested"][0], "x-folder")
        self.assertEqual(expanded["nested"][1]["model"], "gpt://folder/qwen")

    def test_find_model_uses_default_then_first(self):
        models = [{"name": "a"}, {"name": "b", "default": True}]
        self.assertEqual(cli.find_model(models, None)["name"], "b")
        self.assertEqual(cli.find_model([{"name": "a"}], None)["name"], "a")
        self.assertEqual(cli.find_model(models, "a")["name"], "a")
        self.assertIsNone(cli.find_model(models, "missing"))

    def test_template_and_system_message_are_applied(self):
        client = FakeClient(SimpleNamespace(id="resp_1", output_text="ok", output=[]))
        bot = cli.ResponsesBot(dict(MODEL), client=client)
        args = SimpleNamespace(template="wrap", system="expert", param_1="A", param_2=None, param_3=None)
        config = {
            "templates": [{"name": "wrap", "template": "prefix {param_1}: {}"}],
            "system_messages": [{"name": "expert", "message": "Be exact."}],
        }
        cli.configure_template(bot, config, args)
        cli.configure_system(bot, config, args)
        request = bot.build_request("hello")
        self.assertEqual(request["input"], "prefix A: hello")
        self.assertEqual(request["instructions"], "Be exact.")

    def test_build_request_with_image_web_and_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "sample.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            bot = cli.ResponsesBot(dict(MODEL), client=FakeClient(SimpleNamespace(id="r", output_text="ok", output=[])))
            request = bot.build_request(
                "describe",
                image_paths=[str(image)],
                use_web=True,
                web_detail="hi",
                use_code=True,
                stream=True,
                temperature=0.1,
            )
        self.assertTrue(request["stream"])
        self.assertEqual(request["temperature"], 0.1)
        self.assertEqual(request["input"][0]["content"][0], {"type": "input_text", "text": "describe"})
        self.assertEqual(request["input"][0]["content"][1]["type"], "input_image")
        self.assertEqual(request["tools"][0]["search_context_size"], "high")
        self.assertEqual(request["tools"][1]["type"], "code_interpreter")

    def test_streaming_collects_final_response(self):
        final = SimpleNamespace(id="resp_1", output_text="done", output=[])
        events = [
            SimpleNamespace(type="response.output_text.delta", delta="do"),
            SimpleNamespace(type="response.output_text.delta", delta="ne"),
            SimpleNamespace(type="response.completed", response=final),
        ]
        bot = cli.ResponsesBot(dict(MODEL), client=FakeClient(events))
        with redirect_stdout(StringIO()):
            output, saved = bot("hello", stream=True)
        self.assertEqual(output, "done")
        self.assertEqual(saved, [])
        self.assertEqual(bot.previous_response_id, "resp_1")

    def test_download_generated_container_file(self):
        response = {
            "output": [
                {"type": "code_interpreter_call", "container_id": "cntr_1"},
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "annotations": [
                                {
                                    "type": "container_file_citation",
                                    "container_id": "cntr_1",
                                    "file_id": "cfile_1",
                                    "filename": "result.csv",
                                }
                            ],
                        }
                    ],
                },
            ]
        }
        client = FakeClient(response)
        with tempfile.TemporaryDirectory() as tmp:
            saved = cli.download_generated_files(client, response, tmp)
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].name, "result.csv")
            self.assertEqual(saved[0].read_bytes(), b"from-container")
        self.assertEqual(client.containers.files.content.calls, [("cntr_1", "cfile_1")])

    def test_download_generated_file_falls_back_to_files_api(self):
        response = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "annotations": [
                                {
                                    "type": "container_file_citation",
                                    "container_id": "cntr_1",
                                    "file_id": "cfile_1",
                                    "filename": "fallback.txt",
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        client = FakeClient(response)
        client.containers.files.content.fail = True
        with tempfile.TemporaryDirectory() as tmp:
            saved = cli.download_generated_files(client, response, tmp)
            self.assertEqual(saved[0].read_bytes(), b"from-files")


@unittest.skipUnless(
    os.environ.get("api_key") and os.environ.get("folder_id"),
    "Yandex integration tests require api_key and folder_id environment variables",
)
class YandexQwenIntegrationTests(unittest.TestCase):
    def write_config(self, path, params=None):
        config = {
            "models": [
                {
                    "name": "qwen",
                    "model_name": "gpt://%folder_id%/qwen3.5-35b-a3b-fp8",
                    "base_url": "https://ai.api.cloud.yandex.net/v1",
                    "api_key": "%api_key%",
                    "project": "%folder_id%",
                    "default": True,
                    "params": params or {},
                }
            ]
        }
        path.write_text(json.dumps(config), encoding="utf-8")

    def run_yogpt(self, config_path, *args):
        env = os.environ.copy()
        env["YOGPT_CONFIG"] = str(config_path)
        return subprocess.run(
            [sys.executable, "-m", "yogpt.cli", *args],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            text=True,
            capture_output=True,
            timeout=180,
        )

    def test_qwen_basic_cli_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            self.write_config(config_path)
            result = self.run_yogpt(config_path, "-m", "qwen", "Reply with exactly: yogpt-ok")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("yogpt-ok", result.stdout.lower())

    def test_qwen_code_interpreter_downloads_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / "config.json"
            output_dir = tmp_path / "out"
            self.write_config(config_path, {"tool_choice": "required"})
            result = self.run_yogpt(
                config_path,
                "-m",
                "qwen",
                "--code",
                "--output-dir",
                str(output_dir),
                "Use the python tool to create a file named yogpt_numbers.csv containing two columns, n and square, for n=1,2,3. Then answer briefly.",
            )
            files = list(output_dir.glob("*"))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(files, result.stdout)
        self.assertTrue(any(path.name.endswith(".csv") for path in files), [path.name for path in files])


if __name__ == "__main__":
    unittest.main()
