import argparse
import os
import json
from langchain.schema import HumanMessage, SystemMessage, AIMessage
import sys

parser = argparse.ArgumentParser(description='yogpt: LLM command-line interface')
parser.add_argument('--model','-m', type=str, default=None, help='model name')
parser.add_argument('--template','-p', type=str, default=None, help='template to use')
parser.add_argument('--temperature','-t', type=float, default=None, help='model temperature')
parser.add_argument('-1', type=str, default=None, dest='param_1', help='template parameter 1')
parser.add_argument('-2', type=str, default=None, dest='param_2', help='template parameter 2')
parser.add_argument('-3', type=str, default=None, dest='param_3', help='template parameter 3')
parser.add_argument('query', nargs=argparse.REMAINDER)

def load_model(modlist,model_name):
    if modlist is None:
        return None
    model = None
    for m in modlist:
        if (m['name'] == model_name) or (model_name is None and m.get('default',False)):
            model = m
    if model is None:
        return None
    mod = __import__(model['namespace'])
    clss = getattr(mod.chat_models,model['classname'])
    obj = clss(**model['params'])    
    return obj

def find_template(tlist,tname):
    if tlist is None:
        return None
    for t in tlist:
        if t['name']==tname:
            return t
    return None

class ABot:
    def __init__(self,base_model,system_message=None):
        self.GPT = base_model
        self.history = [SystemMessage(content=system_message)]

    def __call__(self, message):
        self.history.append(HumanMessage(content=message))
        res = self.GPT(self.history)
        self.history.append(res)
        return res.content

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

    if args.template is not None:
        t = find_template(config.get('templates',None),args.template)
        if t is None and '{}' in args.template:
            t = { "template" : args.template }
        if t is None:
            print(f"Template {args.template} is not found")
            exit(-1)
        tmpl = t['template']
        for i in range(1,4):
            if getattr(args,f'param_{i}'):
                tmpl = tmpl.replace('{param_'+str(i)+'}',getattr(args,f'param_{i}'))

        trans = lambda x : tmpl.replace('{}',x)
    else:
        trans = lambda x : x
        

    if args.query==['-']:
        print(model([HumanMessage(content=trans(sys.stdin.read()))]).content)
        exit(0)
    elif len(args.query)>0:
        print(model([HumanMessage(content=trans(' '.join(args.query)))]).content)
        exit(0)
    else:
        pass

if __name__ == '__main__':
    main()