import argparse
import base64
import copy
import json
import mimetypes
import os
from pathlib import Path
import re
import sys

from openai import OpenAI


ENV_PATTERN = re.compile(r"%([^%]+)%")
WEB_DETAIL_MAP = {"low": "low", "med": "medium", "hi": "high"}


def build_parser():
    parser = argparse.ArgumentParser(description="yogpt: LLM command-line interface")
    parser.add_argument("--model", "-m", type=str, default=None, help="model name")
    parser.add_argument(
        "--template",
        "-p",
        type=str,
        default=None,
        help='template to use (name from config, "text {}" or @file)',
    )
    parser.add_argument(
        "--system",
        "-s",
        type=str,
        default=None,
        help='system message to use (name from config, "text" or @file)',
    )
    parser.add_argument("--temperature", "-t", type=float, default=None, help="model temperature")
    parser.add_argument("--chat", "-c", action="store_true", default=False, help="initiate follow-up chat")
    parser.add_argument("--image", action="append", default=[], help="image file to add to the request")
    parser.add_argument("--web", action="store_true", default=False, help="enable Responses API web search")
    parser.add_argument(
        "--web-detail",
        choices=["low", "med", "hi"],
        default="med",
        help="web search context size",
    )
    parser.add_argument("--code", action="store_true", default=False, help="enable Code Interpreter")
    parser.add_argument("--output-dir", default=".", help="directory for Code Interpreter output files")
    parser.add_argument("--stream", action="store_true", default=False, help="stream response text as it arrives")
    parser.add_argument("-1", type=str, default=None, dest="param_1", help="template parameter 1")
    parser.add_argument("-2", type=str, default=None, dest="param_2", help="template parameter 2")
    parser.add_argument("-3", type=str, default=None, dest="param_3", help="template parameter 3")
    parser.add_argument("query", nargs=argparse.REMAINDER, help="your query, - for stdin, or @file")
    return parser


def expand_env_vars(value, env=None):
    env = os.environ if env is None else env
    if isinstance(value, str):
        return ENV_PATTERN.sub(lambda match: env.get(match.group(1), match.group(0)), value)
    if isinstance(value, list):
        return [expand_env_vars(item, env) for item in value]
    if isinstance(value, dict):
        return {key: expand_env_vars(item, env) for key, item in value.items()}
    return value


def load_config(path=None):
    if path is None:
        path = os.environ.get("YOGPT_CONFIG") or os.path.join(os.path.expanduser("~"), ".yogpt.config.json")
    try:
        with open(path, encoding="utf-8") as f:
            return expand_env_vars(json.load(f))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Cannot parse config file {path}: {exc}")


def find_model(modlist, model_name):
    if not modlist:
        return None
    if model_name is not None:
        return next((model for model in modlist if model.get("name") == model_name), None)
    return next((model for model in modlist if model.get("default", False)), modlist[0])


def validate_model_config(model):
    if model is None:
        return
    missing = [key for key in ("name", "model_name", "api_key") if not model.get(key)]
    if missing:
        raise ValueError(f"Model {model.get('name', '<unnamed>')} is missing: {', '.join(missing)}")
    if "classname" in model:
        raise ValueError(
            f"Model {model.get('name')} uses obsolete LangChain config. "
            "Use model_name, base_url and api_key instead."
        )


def create_client(model):
    kwargs = {
        "api_key": model["api_key"],
        "base_url": model.get("base_url", "https://api.openai.com/v1"),
    }
    if model.get("project"):
        kwargs["project"] = model["project"]
    if model.get("headers"):
        kwargs["default_headers"] = model["headers"]
    if model.get("timeout") is not None:
        kwargs["timeout"] = model["timeout"]
    if model.get("max_retries") is not None:
        kwargs["max_retries"] = model["max_retries"]
    return OpenAI(**kwargs)


def find_template(tlist, tname):
    if tlist is None:
        return None
    for template in tlist:
        if template["name"] == tname:
            return template
    return None


def find_system(mlist, mname):
    if mlist is None:
        return None
    for message in mlist:
        if message["name"] == mname:
            return message["message"]
    return None


def getfile(fn):
    with open(fn, encoding="utf-8") as f:
        return f.read()


def mapfile(fn):
    if fn.startswith("@"):
        return getfile(fn[1:])
    return fn


def encode_image(path):
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type is None or not mime_type.startswith("image/"):
        raise ValueError(f"Cannot determine supported image MIME type for {path}")
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return {
        "type": "input_image",
        "image_url": f"data:{mime_type};base64,{data}",
    }


def build_input(message, image_paths=None):
    image_paths = image_paths or []
    if not image_paths:
        return message
    content = [{"type": "input_text", "text": message}]
    content.extend(encode_image(path) for path in image_paths)
    return [{"role": "user", "content": content}]


def build_tools(use_web=False, web_detail="med", use_code=False, configured_tools=None):
    tools = list(configured_tools or [])
    if use_web:
        tools.append(
            {
                "type": "web_search",
                "search_context_size": WEB_DETAIL_MAP[web_detail],
            }
        )
    if use_code:
        tools.append({"type": "code_interpreter", "container": {"type": "auto"}})
    return tools


def response_to_dict(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return [response_to_dict(item) for item in value]
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def extract_output_text(response):
    text = getattr(response, "output_text", None)
    if text:
        return text
    data = response_to_dict(response)
    chunks = []
    for item in data.get("output", []) if isinstance(data, dict) else []:
        for content in item.get("content", []) or []:
            if content.get("type") == "output_text" and content.get("text"):
                chunks.append(content["text"])
    return "".join(chunks)


def iter_dicts(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from iter_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_dicts(item)


def extract_generated_files(response):
    data = response_to_dict(response)
    files = {}
    containers = set()

    for obj in iter_dicts(data):
        if obj.get("type") == "code_interpreter_call" and obj.get("container_id"):
            containers.add(obj["container_id"])
        if obj.get("type") == "container_file_citation" and obj.get("file_id"):
            container_id = obj.get("container_id")
            if container_id:
                containers.add(container_id)
            key = (container_id, obj["file_id"])
            files[key] = {
                "container_id": container_id,
                "file_id": obj["file_id"],
                "filename": obj.get("filename") or obj["file_id"],
            }
    return list(files.values()), containers


def list_container_files(client, container_ids, known_files):
    files = {(item.get("container_id"), item["file_id"]): item for item in known_files}
    for container_id in container_ids:
        try:
            page = client.containers.files.list(container_id)
        except Exception:
            continue
        if isinstance(page, dict):
            page_items = page.get("data", [])
        else:
            page_items = getattr(page, "data", [])
        for item in response_to_dict(page_items):
            if item.get("source") not in (None, "assistant"):
                continue
            file_id = item.get("id")
            if not file_id:
                continue
            filename = Path(item.get("path") or file_id).name
            files.setdefault(
                (container_id, file_id),
                {"container_id": container_id, "file_id": file_id, "filename": filename},
            )
    return list(files.values())


def safe_output_path(output_dir, filename):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    name = Path(filename).name or "output"
    candidate = output_dir / name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 1
    while True:
        candidate = output_dir / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def write_binary_response(binary_response, path):
    if hasattr(binary_response, "write_to_file"):
        binary_response.write_to_file(path)
        return
    if hasattr(binary_response, "read"):
        data = binary_response.read()
    elif hasattr(binary_response, "content"):
        data = binary_response.content
    else:
        data = binary_response
    with open(path, "wb") as f:
        f.write(data)


def download_generated_files(client, response, output_dir):
    known_files, containers = extract_generated_files(response)
    files = list_container_files(client, containers, known_files)
    saved = []
    for item in files:
        path = safe_output_path(output_dir, item["filename"])
        try:
            if item.get("container_id"):
                content = client.containers.files.content.retrieve(
                    item["file_id"], container_id=item["container_id"]
                )
            else:
                raise ValueError("No container_id in annotation")
        except Exception:
            content = client.files.content(item["file_id"])
        write_binary_response(content, path)
        saved.append(path)
    return saved


class ResponsesBot:
    def __init__(self, model_config, client=None, system_message=None):
        validate_model_config(model_config)
        self.model_config = model_config
        self.client = client or create_client(model_config)
        self.system_messages = [system_message] if system_message else []
        self.prompt_translator = lambda x: x
        self.previous_response_id = None

    def system_message(self, message):
        self.system_messages.append(message)

    def set_prompt_translator(self, translator):
        self.prompt_translator = translator

    @property
    def instructions(self):
        messages = [message for message in self.system_messages if message]
        return "\n\n".join(messages) if messages else None

    def build_request(
        self,
        message,
        *,
        temperature=None,
        image_paths=None,
        use_web=False,
        web_detail="med",
        use_code=False,
        stream=False,
    ):
        request = copy.deepcopy(self.model_config.get("params", {}))
        configured_tools = request.pop("tools", [])
        tools = build_tools(use_web, web_detail, use_code, configured_tools)
        request.update(
            {
                "model": self.model_config["model_name"],
                "input": build_input(self.prompt_translator(message), image_paths),
                "stream": stream,
            }
        )
        if self.instructions:
            request["instructions"] = self.instructions
        if self.previous_response_id:
            request["previous_response_id"] = self.previous_response_id
        if tools:
            request["tools"] = tools
        if temperature is not None:
            request["temperature"] = temperature
        return request

    def __call__(self, message, **kwargs):
        output_dir = kwargs.pop("output_dir", ".")
        request = self.build_request(message, **kwargs)
        if request.get("stream"):
            response = self._stream_response(request)
        else:
            response = self.client.responses.create(**request)
        self.previous_response_id = getattr(response, "id", None) or self.previous_response_id
        saved = download_generated_files(self.client, response, output_dir)
        return extract_output_text(response), saved

    def _stream_response(self, request):
        final_response = None
        for event in self.client.responses.create(**request):
            event_type = getattr(event, "type", None)
            if event_type == "response.output_text.delta":
                print(getattr(event, "delta", ""), end="", flush=True)
            elif event_type == "response.completed":
                final_response = getattr(event, "response", None)
            elif event_type == "response.failed":
                error = getattr(event, "error", None)
                raise RuntimeError(error or "Streaming response failed")
        print()
        return final_response


def configure_template(bot, config, args):
    if args.template is None:
        return
    if args.template.startswith("@"):
        template = {"template": getfile(args.template[1:])}
    else:
        template = find_template(config.get("templates", None), args.template)
    if template is None:
        if "{}" not in args.template:
            if " " not in args.template:
                print(f"WARNING: Using {args.template} as verbatim template, such name is not in config")
            args.template += " \n{}"
        template = {"template": args.template}
    tmpl = template["template"]
    for i in range(1, 4):
        value = getattr(args, f"param_{i}")
        if value:
            tmpl = tmpl.replace("{param_" + str(i) + "}", value)
    bot.set_prompt_translator(lambda x: tmpl.replace("{}", x))


def configure_system(bot, config, args):
    if args.system is None:
        return
    if args.system.startswith("@"):
        message = getfile(args.system[1:])
    else:
        message = find_system(config.get("system_messages", None), args.system)
    if message is None and " " not in args.system:
        print(f"WARNING: Using {args.system} as verbatim system message, since no such name is found in config")
    bot.system_message(message if message is not None else args.system)


def print_saved_files(saved):
    for path in saved:
        print(f"Saved file: {path}")


def run_query(bot, text, args, include_images=True):
    output, saved = bot(
        text,
        temperature=args.temperature,
        image_paths=args.image if include_images else [],
        use_web=args.web,
        web_detail=args.web_detail,
        use_code=args.code,
        stream=args.stream,
        output_dir=args.output_dir,
    )
    if not args.stream and output:
        print(output)
    print_saved_files(saved)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config()

    model = find_model(config.get("models", None), args.model)
    if model is None:
        print(f"Cannot find model {args.model} in config")
        return -1

    try:
        bot = ResponsesBot(model)
    except ValueError as exc:
        print(exc)
        return -1

    configure_template(bot, config, args)
    configure_system(bot, config, args)

    is_pipe = not os.isatty(sys.stdin.fileno())
    args.query = [mapfile(item) for item in args.query]

    if args.query == ["-"] or (args.query == [] and is_pipe):
        run_query(bot, sys.stdin.read(), args)
        if not args.chat:
            return 0
    elif len(args.query) > 0:
        run_query(bot, " ".join(args.query), args)
        if not args.chat:
            return 0

    while True:
        print(" U> ", end="")
        try:
            q = input()
        except EOFError:
            return 0
        output, saved = bot(
            q,
            temperature=args.temperature,
            image_paths=[],
            use_web=args.web,
            web_detail=args.web_detail,
            use_code=args.code,
            stream=args.stream,
            output_dir=args.output_dir,
        )
        if not args.stream:
            print(f"AI> {output}")
        print_saved_files(saved)


if __name__ == "__main__":
    raise SystemExit(main())
