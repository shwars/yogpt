# yogpt: Command-Line GPT Utility

`yogpt` is a small command-line utility for simple LLM calls from the shell.
It uses the OpenAI-compatible Responses API, so the same command can work with
OpenAI, Yandex AI Studio, or another provider that follows the same API shape.

```bash
pip install yogpt
```

After installation:

```bash
yogpt Hello, how are you today?
```

## Common usage

Ask a question directly:

```bash
yogpt What is the 10th digit of Pi?
```

Pipe stdin into the model:

```bash
echo What is the 10th digit of Pi? | yogpt -
```

If `yogpt` sees piped stdin and no explicit query, it reads stdin automatically:

```bash
cat notes.txt | yogpt -p summarize
```

Read input from a file with `@filename`:

```bash
yogpt @program.py
```

Start an interactive chat:

```bash
yogpt
```

Continue chatting after an initial prompt:

```bash
yogpt -s "You are a software expert. Read this Python program and answer follow-up questions." -c @program.py
```

Select a configured model:

```bash
yogpt -m qwen Explain why sky is blue
```

Set temperature:

```bash
yogpt -t 0.2 Write a short commit message for this change
```

## Templates

Use an inline template. The `{}` placeholder is replaced with the input:

```bash
cat program.py | yogpt -p "Please explain what the following Python code does:{}"
```

Use a named template from `.yogpt.config.json`:

```bash
cat english.txt | yogpt -p translate -1 German -
```

Templates can use `{param_1}`, `{param_2}`, and `{param_3}`, supplied by `-1`,
`-2`, and `-3`.

You can also load a template from a file:

```bash
yogpt -p @prompt.txt @input.txt
```

## System messages

Use a system message directly:

```bash
yogpt -s "You are a concise technical assistant." Explain DNS
```

Use a named system message from the config:

```bash
yogpt -s expert @proposal.md
```

Use a system message from a file:

```bash
yogpt -s @system.txt @input.txt
```

## Images

Attach one or more image files with `--image`:

```bash
yogpt --image screenshot.png "Describe what is wrong in this UI"
yogpt --image before.png --image after.png "Compare these two images"
```

Images are sent as Responses API `input_image` items using base64 data URLs.

## Web search

Enable the Responses API web search tool:

```bash
yogpt --web "What changed in Python recently?"
```

Control search context size:

```bash
yogpt --web --web-detail low "Give a short current answer"
yogpt --web --web-detail hi "Give a detailed current answer with context"
```

`--web-detail med` is the default and maps to the API value `medium`.

## Code Interpreter

Enable Code Interpreter with `--code`:

```bash
yogpt --code "Create a CSV with the numbers 1 to 10 and their squares"
```

If the model creates files, `yogpt` downloads them into the current directory.
Use `--output-dir` to choose another location:

```bash
yogpt --code --output-dir outputs "Create a line chart as a PNG"
```

Generated files are discovered from Code Interpreter output and file citation
annotations. `yogpt` first uses the OpenAI client container file APIs and then
falls back to the regular Files API when needed.

## Streaming

By default, `yogpt` waits for the full response and prints it at once. Use
`--stream` to display text as it is generated:

```bash
yogpt --stream "Write a short story about a command-line tool"
```

## Configuration

Configuration is read from `~/.yogpt.config.json`. For tests or temporary
setups, set `YOGPT_CONFIG` to another JSON file path.

A minimal model entry looks like this:

```json
{
  "name": "gpt",
  "model_name": "gpt-5.5",
  "base_url": "https://api.openai.com/v1",
  "api_key": "%OPENAI_API_KEY%",
  "default": true,
  "params": {
    "reasoning": { "effort": "none" }
  }
}
```

Fields:

* `name`: short model name used with `-m` or `--model`
* `model_name`: model identifier sent to the Responses API
* `base_url`: provider endpoint, defaulting to `https://api.openai.com/v1`
* `api_key`: provider API key
* `project`: optional project or folder ID for providers that need it
* `default`: optional default model marker
* `params`: optional extra fields passed to `responses.create`

Environment variables can be used anywhere in the config with `%NAME%` syntax.
For example, Yandex AI Studio model names usually include the folder ID:

```json
{
  "name": "qwen",
  "model_name": "gpt://%folder_id%/qwen3.5-35b-a3b-fp8",
  "base_url": "https://ai.api.cloud.yandex.net/v1",
  "api_key": "%api_key%",
  "project": "%folder_id%"
}
```

See `sample_config.json` for a fuller starting point with OpenAI and Yandex AI
Studio models, templates, and system messages.

## Config sections

### Models

The `models` array defines available command-line model aliases:

```json
"models": [
  {
    "name": "gpt",
    "model_name": "gpt-5.5",
    "base_url": "https://api.openai.com/v1",
    "api_key": "%OPENAI_API_KEY%",
    "default": true
  }
]
```

### Templates

The `templates` array defines reusable prompt templates:

```json
{
  "name": "translate",
  "template": "Please, translate the text in triple backquotes below into the following language: {param_1}. Here is the text:\n```{}```"
}
```

If a template name is not found and the value has no spaces or `{}` placeholder,
`yogpt` prints a warning and treats it as a literal template.

### System messages

The `system_messages` array defines reusable model instructions:

```json
{
  "name": "expert",
  "message": "You are a careful technical expert. Give precise, practical answers and call out assumptions."
}
```

If a system message name is not found and the value has no spaces, `yogpt`
prints a warning and treats it as a literal system message.
