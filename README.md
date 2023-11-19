# yogpt: Command-Line GPT Utility

This utility has been created to provide support for all chat large language models supported by LangChain framework. You can install it by using

```bash
pip install yogpt
```

After this, you can invoke it just by calling `yogpt`:

```bash
yogpt Hello, how are you today?
```

## Sample usage

There are four main scenarios how `yogpt` is normally used:

* By asking the question directly on the command line `yogpt What is the 10th digit of Pi?`
* By piping stdin into `yogpt`: `echo What is the 10th digit of Pi | yogpt -`. If `yogpt` understands that it is invoked in the pipe, it will automatically assume `-` parameter, so it can be omitted.
* By calling `yogpt` without input - this initiates console chat.
* If you want to further chat with `yogpt` after providing it with some input, you may specify `-c`/`--chat` flag. In this case it will consume input as first utterance to the bot, and then initiate a follow-up chat. For example:

```
yogpt -s "You are a software expert. Please read python program provided and be ready to answer questions on this program." -c @program.py
```

The example above also shows that you can use `@filename` syntax to get input from a file.

You can specify different models using `-m`/`--model` parameter. Possible models (including your personal credentials) should be specified in the config file (see details below).

You can also use prompt templates. Here is an example that will explain what a Python program does:

```bash
cat program.py | yogpt -p "Please explain what the following Python code does:{}"
```

Some prompt templates that you often use can be defined in the config file, and used just by specifying the template name (with some optional additional parameters):

```bash
cat english.txt | yogpt -p translate -1 german -
```

You can also use `@filename` syntax to get prompt template from a filename.

You can specify system message using `-s`/`--system` switch. Similarly, it can be a name from config file, `@filename`, or verbatim system message in quotes.

## Specifying credentials

All utility configuration is stored in the user's home directory in the `.yogpt.config.json` file. A sample config file is provided in this repository, which you may use as a starting point.

Config file specifies the following sections:

### Models

Each model is defined by the following JSON snippet:

```json
{
    "name" : "ygpt",
    "classname" : "langchain.chat_models.ChatYandexGPT",
    "default" : true,
    "params" : { "api_key" : "..." }
}
```
Here parameters mean the following:
* `name` is the model name, which you can specify using `-m` or `--model` parameter of the utility
* `classname` is the full class name of the model class
* `params` is the dictionary with all the parameters that we pass to the class when creating the model. Depending on the model, there will probably be your personal credentials here, such as OpenAI API Key.

### Templates

To carry out some specific tasks, you can define templates in the same config file using `templates` section. Template definition looks like this:

```json
{
    "name" : "translate",
    "template" : "Please, translate the text in triple backquotes below into the following language: {param_1}. Here is the text:\n```{}```"
}
```
* `name` is the name of the template that you can pass to `-p` or `--template` parameter.
* `template` is the template itself. In this template, `{param_1}` through `{param_3}` are replaced by optional command-line parameters `-1` through `-3`, and `{}` is replaced by the user's query.

You can also pass the actual template text to `-p`/`--template` parameter, like in the following example:

```bash
echo Hello, how are you? | yogpt -p "Translate the following text into Chinese: {}" -
```

Have a look into sample config file for different templates that you can use in your setup.

> If you by mistake make a typo in the system message name when specifying `--template` parameter, this word would be used as verbatim template, which may cause problems. If there are no spaces or `{}` characters in the specified template, and if the name is not found in config, a warning is printed.

### System Messages

Bot system messages are in a way similar to templates. They define overall behavior of LLM. For example, you can use system message to set the tone of the conversation, or to specify task for the model to perform.

System message can be specified on the command-line using `--system "..."` or `-s "..."` switch. You can also use `@filename` syntax to supply the filename, or use system message name to look it up in the config file.

> If you by mistake make a typo in the system message name, this word would be used as verbatim system message, which may cause problems. If there are no spaces in the specified system message, and if the name is not found in config, a warning is printed.

Config section for system messages looks like this:

```json
"system_messages" : [
    {
        "name" : "rude",
        "message" : "You are extremely rude chatbot that does not want to talk to anyone."
    }
]
```
