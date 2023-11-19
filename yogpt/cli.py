import argparse
import os
import json
from langchain.schema import HumanMessage, SystemMessage, AIMessage
import sys

parser = argparse.ArgumentParser(description='yogpt: LLM command-line interface')
parser.add_argument('--model','-m', type=str, default=None, help='model name')
parser.add_argument('--template','-p', type=str, default=None, help='template to use (name from config, "text {}" or @file)')
parser.add_argument('--system','-s',type=str,default=None,help='system message to use (name from config, "text" or @file)')
parser.add_argument('--temperature','-t', type=float, default=None, help='model temperature')
parser.add_argument('--chat','-c', action='store_true', default=False, help='initiate follow-up chat')
parser.add_argument('-1', type=str, default=None, dest='param_1', help='template parameter 1')
parser.add_argument('-2', type=str, default=None, dest='param_2', help='template parameter 2')
parser.add_argument('-3', type=str, default=None, dest='param_3', help='template parameter 3')
parser.add_argument('query', nargs=argparse.REMAINDER, help='your query, - for stdin, or @file')

def load_model(modlist,model_name):
    if modlist is None:
        from yogpt.g4f import G4FModel
        return G4FModel()
    model = None
    for m in modlist:
        if (m['name'] == model_name) or (model_name is None and m.get('default',False)):
            model = m
    if model is None:
        return None
    mpath = model['classname'].split('.')
    mod = __import__('.'.join(mpath[:-1]))
    for x in mpath[1:]:
        mod = getattr(mod,x)
    obj = mod(**model['params'])    
    return obj

def find_template(tlist,tname):
    if tlist is None:
        return None
    for t in tlist:
        if t['name']==tname:
            return t
    return None

def find_system(mlist,mname):
    if mlist is None:
        return None
    for m in mlist:
        if m['name']==mname:
            return m['message']
    return None


def getfile(fn):
    return open(fn).read()

def mapfile(fn):
    if fn.startswith('@'):
        return getfile(fn[1:])
    else:
        return fn

class ABot:
    def __init__(self,base_model,system_message=None):
        self.GPT = base_model
        self.history = [SystemMessage(content=system_message)] if system_message else []
        self.prompt_translator = lambda x : x

    def __call__(self, message):
        self.history.append(HumanMessage(content=self.prompt_translator(message)))
        res = self.GPT(self.history)
        self.history.append(res)
        return res.content

    def system_message(self,message):
        self.history.append(SystemMessage(content=message))

    def set_prompt_translator(self,translator):
        self.prompt_translator = translator

def main():
    try:
        config = json.load(open(os.path.join(os.path.expanduser('~'),'.yogpt.config.json')))
    except:
        config = {}

    args = parser.parse_args()

    model = load_model(config.get("models",None),args.model)
    if args.temperature:
        model.temperature = args.temperature

    if model is None:
        print(f"Cannot find model {args.model} in config")
        exit(-1)

    bot = ABot(model)

    if args.template is not None:
        if args.template.startswith("@"):
            t = { "template" : getfile(args.template[1:]) }
        else:
            t = find_template(config.get('templates',None),args.template)
        if t is None:
            if '{}' not in args.template:
                if ' ' not in args.template:
                    print(f"WARNING: Using {args.template} as verbatim template, such name is not in config")
                args.template += " \n{}"
                
            t = { "template" : args.template }
        if t is None:
            print(f"Template {args.template} is not found")
            exit(-1)
        tmpl = t['template']
        for i in range(1,4):
            if getattr(args,f'param_{i}'):
                tmpl = tmpl.replace('{param_'+str(i)+'}',getattr(args,f'param_{i}'))
        
        bot.set_prompt_translator(lambda x : tmpl.replace('{}',x))

    if args.system is not None:
        if args.system.startswith("@"):
            m = getfile(args.system[1:])
        else:
            m = find_system(config.get('system_messages',None),args.system)
        if m is None and ' ' not in args.system:
            print(f'WARNING: Using {args.system} as verbatim system message, since no such name is found in config')
        bot.system_message(m if m is not None else args.system)

    is_pipe = not os.isatty(sys.stdin.fileno())

    args.query = [ mapfile(x) for x in args.query ]

    if args.query==['-'] or (args.query==[] and is_pipe):
        print(bot(sys.stdin.read()))
        if not args.chat:
            exit(0)
    elif len(args.query)>0:
        print(bot(' '.join(args.query)))
        if not args.chat:
            exit(0)
    
    while True:
        print(" U> ",end='')
        q = input()
        a = bot(q)
        print(f"AI> {a}")

if __name__ == '__main__':
    main()