from pathlib import Path
import argparse
import sys, copy
import networkx as nx
from lib.conll import CoNLLReader
from collections import Counter, defaultdict

parser = argparse.ArgumentParser(description="""Convert conllu to conll format""")
#parser.add_argument('--input', help="conllu file", default='../data/UD_Catalan_frozen/ca-ud-')
parser.add_argument('--input', help="conllu file", default='../data/UD_Spanish-AnCora_frozen/es_ancora-ud-')

args = parser.parse_args()


underscore_counter = Counter()
treebank = []


wordcounter=defaultdict(dict)



for ext in "dev.conllu test.conllu train.conllu".split():
    infile = args.input+ext
    cio = CoNLLReader()
    treebank = treebank + cio.read_conll_u(infile)#, args.keep_fused_forms, args.lang, POSRANKPRECEDENCEDICT)


for s in treebank:
    for n in s.nodes()[1:]:
        lemma = s.node[n]['lemma']
        form = s.node[n]['form']
        cpostag = s.node[n]['cpostag']
        feats = s.node[n]['feats']

        if len(lemma) > 2 and "_" in lemma:
            if cpostag == "DET":
                action = 'shared'
            else:
                action = 'leftmost'
            underscore_counter[(form,cpostag,lemma,feats,action)]+=1
        else:
            wordcounter[form][cpostag]=[lemma,feats]


for x in underscore_counter.most_common(10):
    form,cpostag,lemma,feats,action = x[0]
    #print("\t".join(x[0])+'\t'+str(x[1]))
    e="_"
    rightindex = str(1+lemma.count("_"))
    outline="\t".join(["1-"+rightindex,form,lemma,cpostag,e,feats,'0','dep',e,action])
    print(outline)
    counter=0
    for part in lemma.split("_"):
        counter+=1
        for k in wordcounter[part]:
            formpart=part
            pospart=k
            lemmapart=wordcounter[part][k][0]
            featspart=wordcounter[part][k][1]

            if cpostag == "DET":
                label = 'det'
            elif counter == 1:
                label = 'dep'
            else:
                label = 'mwe'

            if action == 'shared' or counter == 1:
                head = "0"
            else:
                head = "1"

            outline="\t".join([str(counter),formpart,lemmapart,pospart,e,featspart,head,label,e,action])
            print(outline)
    print()



