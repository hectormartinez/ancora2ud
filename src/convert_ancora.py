from collections import defaultdict
from itertools import islice
from pathlib import Path
import argparse
import sys, copy
import networkx as nx
from lib.conll import CoNLLReader


def remove_elliptic_subjects(sent):
  newsent = copy.copy(sent)
  elliptic_subjects=[i for i in newsent.nodes() if newsent.node[i]['form'] == '_' and newsent[newsent.head_of(i)][i]['deprel']=='nsubj']

  while elliptic_subjects:
    toprint=True
    newsent=newsent.sentence_minus_word(elliptic_subjects[0])
    elliptic_subjects=[i for i in newsent.nodes() if newsent.node[i]['form'] == '_' and newsent[newsent.head_of(i)][i]['deprel']=='nsubj']

  return newsent

def add_mwe_to_tree(sent,mwe_id,mw_form,mw_lemma,mw_cpos):
    ### fetches info from mwe dict and constructs a new tree
    values=mwedict.get(mw_lemma,"MISSING_MWE")
    if values == "MISSING_MWE":
        print("ADD to mwe-info: ",mw_lemma, mw_form)
        #just add original node, do nothing for now
        sent.node[mwe_id]["lemma"] = mw_lemma.replace("_","-")
        sent.node[mwe_id]["word"] = mw_form.replace("_","-")
        return sent

    newsent = nx.DiGraph()
    mw_numtoks = len(mw_lemma.split("_"))
    offset=mw_numtoks-1 # offset of successor indices

    ## add nodes
    for node_id in sent.nodes():
        if node_id==0:
            continue
        head_id=head_of(sent,node_id)
        deprel=sent[head_id][node_id]['deprel']

        if node_id == mwe_id:
            ## process mwe
            mwparts = mw_form.split("_")
            mwe_head=head_id # head of previous mwe token
            # check if head is after mwe_id
            if mwe_head>node_id:
                mwe_head+=offset
            mwe_first=node_id  # head of the mw construction after splitting
            for i,part in enumerate(mwparts):
                new_id=mwe_first+i
                # construct new node
                newvalues={}
                newvalues={'phead': '_', 'pdeprel': '_', 'cpos': mw_cpos, 'pos': '_'}
                newvalues['lemma']=part
                ## values:
                ## ['I ADP AdpType=Prep', 'går NOUN Definite=Ind|Gender=Neut|Number=Sing']
                newvalues['word']=mwparts[i]
                newvalues['lemma']=values[i].split()[0]
                newvalues['cpos']=values[i].split()[1]
                newvalues['feats']=values[i].split()[2]

                newsent.add_node(new_id,newvalues)
                if i==0: #first node is head of whole
                    newsent.add_edge(mwe_head,new_id,deprel=deprel)#inherit old deprel
                else:
                    if newvalues['cpos'] == "X":
                        newdeprel="foreign"
                    else:
                        newdeprel="mwe"
                    newsent.add_edge(mwe_first,new_id,deprel=newdeprel)
        else:
            if node_id < mwe_id:
                # we are on the left of the mwe
                new_node_id = node_id
                # check if we need to move head_id
                if head_id > mwe_id and head_id != 0:
                    head_id += offset

            elif node_id > mwe_id:
                # we are right of the mwe
                # add offset
                new_node_id=node_id+offset
                # check if we need to move head_id,too
                if head_id > mwe_id:
                    head_id += offset

            newsent.add_node(new_node_id,sent.node[node_id])
            newsent.add_edge(head_id,new_node_id,deprel=deprel)
    return newsent



def remove_longpos(sent):
    newsent = copy.copy(sent)
    for n in newsent.nodes()[1:]:
        newsent.node[n]['postag'] = '_'

    return newsent

def split_adpdet_contractions(sent):

    contraction_prep={'al': 'a', 'del':'de','pel':'per'}

    newsent = copy.copy(sent)


    adpdet_contractions=[i for i in newsent.nodes() if newsent.node[i]['lemma'] in contraction_prep and newsent.node[i]['cpostag']=='ADP']
    while adpdet_contractions:
        #if 'multi_tokens' not in newsent.graph.keys():
        #    newsent.graph['multi_tokens'] = {}
        current_contraction_index=adpdet_contractions[0]
        newsent.graph['multi_tokens'][current_contraction_index]={'id':[current_contraction_index,current_contraction_index+1],'form':newsent.node[current_contraction_index]['form']}
        newsent = copy.copy(newsent.sentence_plus_word(adpdet_contractions[0],{'form':'***','cpostag':'***', 'lemma':'***','feats':"_"},newsent.head_of(current_contraction_index),{'deprel':'det'}))

        newsent.node[current_contraction_index]['form']=contraction_prep[newsent.node[current_contraction_index]['lemma']]
        newsent.node[current_contraction_index]['form']=contraction_prep[newsent.node[current_contraction_index]['lemma']]
        newsent.node[current_contraction_index]['lemma']=contraction_prep[newsent.node[current_contraction_index]['lemma']]
        newsent.node[current_contraction_index]['cpostag']='ADP'
        newsent.node[current_contraction_index]['feats']='AdpType=Prep'

        if newsent.node[current_contraction_index+1]['form'].endswith('s'):
            newsent.node[current_contraction_index+1]['feats']='Definite=Def|Gender=Masc|Number=Plur|PronType=Art'
            newsent.node[current_contraction_index+1]['form']='els'
        else:
            newsent.node[current_contraction_index+1]['feats']='Definite=Def|Gender=Masc|Number=Sing|PronType=Art'
            newsent.node[current_contraction_index+1]['form']='el'
        newsent.node[current_contraction_index+1]['lemma']='el'
        newsent.node[current_contraction_index+1]['cpostag']='DET'

        adpdet_contractions=[i for i in newsent.nodes() if newsent.node[i]['lemma'] in contraction_prep and newsent.node[i]['cpostag']=='ADP']

    if 'multi_tokens' not in newsent.graph.keys():
        print(newsent.graph.keys())
    return newsent

def split_underscored_token(sent):
    newsent = copy.copy(sent)

    return newsent


def apply_transform(sent):
    newsent = copy.copy(sent)
    newsent = remove_elliptic_subjects(sent)
    #newsent = remove_longpos(newsent)
    newsent = copy.copy(split_adpdet_contractions(newsent))
    #newsent = split_underscored_token(newsent)
    return newsent


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
    modif_treebank = []
    for s in orig_treebank:
        s = copy.copy(apply_transform(s))
        #if not 'multi_tokens' in s.graph.keys():
        #    print(s.get_sentence_as_string())
        modif_treebank.append(s)
    cio.write_conll(modif_treebank,args.output,conllformat='conllu', print_fused_forms=True,print_comments=True)

if __name__ == "__main__":
    main()
