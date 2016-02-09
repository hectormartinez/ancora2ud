from collections import defaultdict
from itertools import islice
from pathlib import Path
import argparse
import sys, copy

from lib.conll import CoNLLReader


def remove_elliptic_subjects(sent):
  newsent = copy.copy(sent)
  elliptic_subjects=[i for i in newsent.nodes() if newsent.node[i]['form'] == '_' and newsent[newsent.head_of(i)][i]['deprel']=='nsubj']

  while elliptic_subjects:
    toprint=True
    newsent=newsent.sentence_minus_word(elliptic_subjects[0])
    elliptic_subjects=[i for i in newsent.nodes() if newsent.node[i]['form'] == '_' and newsent[newsent.head_of(i)][i]['deprel']=='nsubj']

  return newsent

def remove_longpos(sent):
    newsent = copy.copy(sent)
    for n in newsent.nodes()[1:]:
        newsent.node[n]['postag'] = '_'

    return newsent

def split_adpdet_contractions(sent):
    newsent = copy.copy(sent)
    return newsent

def split_functional_mwe(sent):
    newsent = copy.copy(sent)
    return newsent


def apply_transform(sent):
    sent = remove_elliptic_subjects(sent)
    sent = remove_longpos(sent)
    sent = split_adpdet_contractions(sent)
    sent = split_functional_mwe(sent)
    return sent


def main():
    parser = argparse.ArgumentParser(description="""Convert conllu to conll format""")
    parser.add_argument('--input', help="conllu file", default='../data/UD_Catalan_frozen/ca-ud-dev.conllu')
    parser.add_argument('--output', help="target file", type=Path,default="catout.conllu")
    parser.add_argument('--lang', help="specify a language 2-letter code", default="default")
    args = parser.parse_args()

    if sys.version_info < (3,0):
        print("Sorry, requires Python 3.x.") #suggestion: install anaconda python
        sys.exit(1)

    cio = CoNLLReader()
    orig_treebank = cio.read_conll_u(args.input)#, args.keep_fused_forms, args.lang, POSRANKPRECEDENCEDICT)
    modif_treebank = copy.copy(orig_treebank)
    for s in modif_treebank:
        s = apply_transform(s)
    cio.write_conll(modif_treebank,args.output)

if __name__ == "__main__":
    main()
