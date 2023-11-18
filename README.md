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

There are three main scenarios how `yogpt` is normally used:

* By asking the question directly on the command line `yogpt What is the 10th digit of Pi?`
* By piping stdin into `yogpt`: `echo What is the 10th digit of Pi | yogpt -`
* By calling `yogpt` without input - this initiates console chat.

You can specify different models using `-m`/`--model` parameter. Possible models (including your personal credentials) should be specified in the config file (see details below).

You can also use prompt templates. Here is an example that will explain what a Python program does:

```bash
cat program.py | yogpt -p "Please explain what the following Python code does:{}" -
```

Some prompt templates that you often use can be defined in the config file, and used just by specifying the template name (with some optional additional parameters):

```bash
cat english.txt | yogpt -p translate -1 german -
```

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
