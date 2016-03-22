from collections import defaultdict
from itertools import islice
from pathlib import Path
import argparse
import sys, copy
import networkx as nx
from lib.conll import CoNLLReader



doublecliticverbs_fused = "imaginaros quitárselas afeitárselo plantearselo vérselas planteárnoslo arrebatándoselo jugársela vérselas aplicárseles ganárselo vendérsela".split()
doublecliticverbs_split = ["imaginar os","quitar se las","afeitar se lo","plantear se lo","ver se las","plantear nos lo", "arrebatando se lo","jugar se la","ver se las","aplicar se les", "ganar se lo","vender se la"]

doublecliticverbs = dict([(x,y.split()) for x,y in zip(doublecliticverbs_fused,doublecliticverbs_split)])

twocharclitics = "me te le la lo se".split(" ") # "os" generates too many false positives
threecharclitics = "nos les los las".split(" ")
doublecaseclitics = "le les nos os se te me".split(" ")

cliticlemmas = {"me": "yo", "te": "tú", "la":"él", "las":"él","los":"él","lo":"él","nos":"yo","se":"él","le":"él","les":"él", "os":"tú"}

VERBALPOS = "AUX VERB".split()
catalanverbclitic_forms = "'hi 'ho 'l 'ls 'm 'n 'ns 's -hi -ho -l -la -les -li -lo -los -m -me -ne -nos -s -s' -se -te".split()

"""
1	la	él	PRON	PRON	Case=Acc|Gender=Fem|Number=Sing|Person=3|PronType=Prs	_	dobj	_	_
1	las	él	PRON	PRON	Case=Acc|Gender=Fem|Number=Plur|Person=3|PronType=Prs	22	dobj	_	_
1	lo	él	PRON	PRON	Case=Acc|Gender=Masc|Number=Sing|Person=3|PronType=Prs	11	dobj	_	_
1	los	él	PRON	PRON	Case=Acc|Gender=Masc|Number=Plur|Person=3|PronType=Prs	23	dobj	_	_
19	le	él	PRON	PRON	Case=Dat|Number=Sing|Person=3|PronType=Prs	20	iobj	_	_
4	se	él	PRON	PRON	Person=3	5	iobj/dobj	_	_
9	nos	yo	PRON	PRON	Number=Plur|Person=1|PronType=Prs	10	iobj/dobj	_	_
3	te	tú	PRON	PRON	Number=Sing|Person=2|PronType=Prs	4	iobj/dobj	_	_
17	os	tú	PRON	PRON	Number=Plur|Person=2|PronType=Prs	18	iobj	_	_
2	me	yo	PRON	PRON	Number=Sing|Person=1|PronType=Prs	3	iobj/dobj	_	_

"""
cliticfeatures={}
cliticfeatures["la"]= "Number=Sing|Person=2|PronType=Prs"
cliticfeatures["las"]= "Case=Acc|Gender=Fem|Number=Plur|Person=3|PronType=Prs"
cliticfeatures["lo"]= "Case=Acc|Gender=Masc|Number=Sing|Person=3|PronType=Prs"
cliticfeatures["los"]= "Case=Acc|Gender=Masc|Number=Plur|Person=3|PronType=Prs"
cliticfeatures["le"]= "Case=Dat|Number=Sing|Person=3|PronType=Prs"
cliticfeatures["les"]= "Case=Dat|Number=Plur|Person=3|PronType=Prs"
cliticfeatures["se"]= "Person=3"
cliticfeatures["nos"]= "Number=Plur|Person=1|PronType=Prs"
cliticfeatures["te"]= "Number=Plur|Person=2|PronType=Prs"
cliticfeatures["os"]= "Number=Sing|Person=2|PronType=Prs"
cliticfeatures["me"]= "Number=Sing|Person=1|PronType=Prs"


exclusion_list_verbs_es = set("pase cancele humanos compromete cueste aumente acumula cumpla Presume revise facilite evite hable cueste admite ahuyente despiste equivale aporte".split())

def remove_elliptic_subjects(sent):
  newsent = copy.copy(sent)
  elliptic_subjects=[i for i in newsent.nodes() if newsent.node[i]['form'] == '_' and newsent[newsent.head_of(i)][i]['deprel']=='nsubj']

  while elliptic_subjects:
    toprint=True
    newsent=newsent.sentence_minus_word(elliptic_subjects[0])
    elliptic_subjects=[i for i in newsent.nodes() if newsent.node[i]['form'] == '_' and newsent[newsent.head_of(i)][i]['deprel']=='nsubj']

  return newsent


def verb_has_object(sent,verbindex):
    for h,d in sent.edges():
        if h == verbindex and sent[h][d]["deprel"] == "dobj":
            return True
    return False

def adp_introduces_mwe(sent,adpositionindex):
    for h,d in sent.edges():
        if h == adpositionindex and sent[h][d]["deprel"] == "mwe":
            return True
    return False

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
        contracted_prep = newsent.node[current_contraction_index]["form"]
        if adp_introduces_mwe(newsent,current_contraction_index):
            newsent.graph['multi_tokens'][current_contraction_index]={'id':[current_contraction_index,current_contraction_index+1],'form':newsent.node[current_contraction_index]['form']}
            newsent = copy.copy(newsent.sentence_plus_word(current_contraction_index,{'form':'***','cpostag':'***', 'lemma':'***','feats':"_"},current_contraction_index,{'deprel':'mwe'}))

        else:
            newsent.graph['multi_tokens'][current_contraction_index]={'id':[current_contraction_index,current_contraction_index+1],'form':newsent.node[current_contraction_index]['form']}

            label = "det"
            if adp_introduces_mwe(newsent,newsent.head_of(current_contraction_index)): #if within a MWE index
                label = "mwe"
            newsent = copy.copy(newsent.sentence_plus_word(current_contraction_index,{'form':'***','cpostag':'***', 'lemma':'***','feats':"_"},newsent.head_of(current_contraction_index),{'deprel':label}))

        newsent.node[current_contraction_index]['form']=contraction_prep[newsent.node[current_contraction_index]['lemma']]
        newsent.node[current_contraction_index]['form']=contraction_prep[newsent.node[current_contraction_index]['lemma']]
        newsent.node[current_contraction_index]['lemma']=contraction_prep[newsent.node[current_contraction_index]['lemma']]
        newsent.node[current_contraction_index]['cpostag']='ADP'
        newsent.node[current_contraction_index]['feats']='AdpType=Prep'

        if contracted_prep.endswith('s'):
            newsent.node[current_contraction_index+1]['feats']='Definite=Def|Gender=Masc|Number=Plur|PronType=Art'
            newsent.node[current_contraction_index+1]['form']='els'
        else:
            newsent.node[current_contraction_index+1]['feats']='Definite=Def|Gender=Masc|Number=Sing|PronType=Art'
            newsent.node[current_contraction_index+1]['form']='el'
        newsent.node[current_contraction_index+1]['lemma']='el'
        newsent.node[current_contraction_index+1]['cpostag']='DET'
        newsent.node[current_contraction_index+1]['postag']='DET'


        adpdet_contractions=[i for i in newsent.nodes() if newsent.node[i]['lemma'] in contraction_prep and newsent.node[i]['cpostag']=='ADP']# and not adp_introduces_mwe(newsent,i)]

    if 'multi_tokens' not in newsent.graph.keys():
        print(newsent.graph.keys())
    return newsent


def insert_multitoken_verbs_ca(sent):
    newsent = copy.copy(sent)
    verbs_with_possible_clitic = [i for i in newsent.nodes()[1:] if ("Mood=Imp" in newsent.node[i]['feats'] or "VerbForm=Ger" in newsent.node[i]['feats'] or "VerbForm=Inf" in newsent.node[i]['feats']) and (newsent.node[i]['cpostag'] == "VERB" or newsent.node[i]['cpostag'] == "AUX") and newsent.node[i+1]['form'].lower() in catalanverbclitic_forms]
    for vindex in verbs_with_possible_clitic:
        acc =  [newsent.node[vindex]["form"]]
        for suf in range(vindex+1,vindex+4):
            if suf in newsent.nodes() and newsent.node[suf]["form"] in catalanverbclitic_forms:
                acc.append(newsent.node[suf]["form"])
                rightindex = suf
            else:
                break
        newsent.graph['multi_tokens'][vindex]= {'id':(vindex,rightindex),'form':"".join(acc)}

    return newsent

def process_mwe_verbs(sent):
    #For Spanish, identify if the verb is a non-finite form like "encontrárselas" and split into its forming subtokens
    """
    Remember "Vérselas" "ocultándoselo"
    """
    newsent = copy.copy(sent)
    doublecaseclitics = []

    verbs_doubleclitic = [i for i in newsent.nodes()[1:] if ("Mood=Imp" in newsent.node[i]['feats'] or "VerbForm=Ger" in newsent.node[i]['feats'] or "VerbForm=Inf" in newsent.node[i]['feats']) and (newsent.node[i]['cpostag'] == "VERB" or newsent.node[i]['cpostag'] == "AUX") and newsent.node[i]['form'].lower() in doublecliticverbs]
    while verbs_doubleclitic:
        current_verb=verbs_doubleclitic[0]
        if len(doublecliticverbs[newsent.node[current_verb]['form']]) == 3:
            verbform = doublecliticverbs[newsent.node[current_verb]['form']][0]
            firstclitic = doublecliticverbs[newsent.node[current_verb]['form']][2]
            secondclitic = doublecliticverbs[newsent.node[current_verb]['form']][1]
            newsent.graph['multi_tokens'][current_verb]= {'id':(current_verb,current_verb+1),'form':newsent.node[current_verb]['form']}
            newsent = copy.copy(newsent.sentence_plus_word(current_verb,{'form':firstclitic,'cpostag':"PRON", 'postag':"PRON",'lemma':cliticlemmas[firstclitic.lower()],'feats':cliticfeatures[firstclitic]},current_verb,{'deprel':'iobj'}))
            newsent = copy.copy(newsent.sentence_plus_word(current_verb,{'form':secondclitic,'cpostag':"PRON", 'postag':"PRON",'lemma':cliticlemmas[secondclitic.lower()],'feats':cliticfeatures[secondclitic]},current_verb,{'deprel':'dobj'}))
            newsent.node[current_verb]['form']=verbform
        else:
            verbform = doublecliticverbs[newsent.node[current_verb]['form']][0]
            firstclitic = doublecliticverbs[newsent.node[current_verb]['form']][1]
            newsent.graph['multi_tokens'][current_verb]= {'id':(current_verb,current_verb+1),'form':newsent.node[current_verb]['form']}
            newsent = copy.copy(newsent.sentence_plus_word(current_verb,{'form':firstclitic,'cpostag':"PRON", 'postag':"PRON",'lemma':cliticlemmas[firstclitic.lower()],'feats':cliticfeatures[firstclitic]},current_verb,{'deprel':'iobj'}))
            newsent.node[current_verb]['form']=verbform

        verbs_doubleclitic = [i for i in newsent.nodes()[1:] if ("Mood=Imp" in newsent.node[i]['feats'] or "VerbForm=Ger" in newsent.node[i]['feats'] or "VerbForm=Inf" in newsent.node[i]['feats']) and (newsent.node[i]['cpostag'] == "VERB" or newsent.node[i]['cpostag'] == "AUX") and newsent.node[i]['form'].lower() in doublecliticverbs]

    verbs_3hclitic=[i for i in newsent.nodes()[1:] if ("Mood=Imp" in newsent.node[i]['feats'] or "VerbForm=Ger" in newsent.node[i]['feats'] or "VerbForm=Inf" in newsent.node[i]['feats']) and newsent.node[i]['cpostag']in VERBALPOS and newsent.node[i]['form'][-3:] in threecharclitics and newsent.node[i]['form'] not in exclusion_list_verbs_es]
    while verbs_3hclitic:
        current_verb=verbs_3hclitic[0]
        verb_has_dobj = verb_has_object(newsent,current_verb)
        newform = newsent.node[current_verb]["form"][:-3].replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")
        clitic =  newsent.node[current_verb]["form"][-3:]

        if clitic not in doublecaseclitics:
            cliticlabel = "dobj"
        elif verb_has_dobj:
            cliticlabel = "iobj"
        else:
            cliticlabel = "dobj"

        newsent.graph['multi_tokens'][current_verb]= {'id':(current_verb,current_verb+1),'form':newsent.node[current_verb]['form']}
        newsent = copy.copy(newsent.sentence_plus_word(current_verb,{'form':clitic,'cpostag':"PRON", 'postag':"PRON",'lemma':cliticlemmas[clitic.lower()],'feats':cliticfeatures[clitic]},current_verb,{'deprel':cliticlabel}))
        newsent.node[current_verb]['form']=newform
        verbs_3hclitic=[i for i in newsent.nodes()[1:] if ("Mood=Imp" in newsent.node[i]['feats'] or "VerbForm=Ger" in newsent.node[i]['feats'] or "VerbForm=Inf" in newsent.node[i]['feats']) and (newsent.node[i]['cpostag'] == "VERB" or newsent.node[i]['cpostag'] == "AUX") and newsent.node[i]['form'][-3:] in threecharclitics and newsent.node[i]['form'] not in exclusion_list_verbs_es]

    verbs_2chclitic=[i for i in newsent.nodes()[1:] if ("Mood=Imp" in newsent.node[i]['feats'] or "VerbForm=Ger" in newsent.node[i]['feats'] or "VerbForm=Inf" in newsent.node[i]['feats']) and (newsent.node[i]['cpostag'] == "VERB" or newsent.node[i]['cpostag'] == "AUX") and newsent.node[i]['form'][-2:] in twocharclitics and newsent.node[i]['form'] not in exclusion_list_verbs_es]
    while verbs_2chclitic:
        current_verb=verbs_2chclitic[0]
        verb_has_dobj = verb_has_object(newsent,current_verb)
        newform = newsent.node[current_verb]["form"][:-2].replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")
        clitic =  newsent.node[current_verb]["form"][-2:]

        if clitic not in doublecaseclitics:
            cliticlabel = "dobj"
        elif verb_has_dobj:
            cliticlabel = "iobj"
        else:
            cliticlabel = "dobj"

        newsent.graph['multi_tokens'][current_verb]= {'id':(current_verb,current_verb+1),'form':newsent.node[current_verb]['form']}
        newsent = copy.copy(newsent.sentence_plus_word(current_verb,{'form':clitic,'cpostag':"PRON",'postag':"PRON", 'lemma':cliticlemmas[clitic.lower()],'feats':cliticfeatures[clitic]},current_verb,{'deprel':cliticlabel}))
        newsent.node[current_verb]['form']=newform
        verbs_2chclitic=[i for i in newsent.nodes()[1:] if ("Mood=Imp" in newsent.node[i]['feats'] or "VerbForm=Ger" in newsent.node[i]['feats'] or "VerbForm=Inf" in newsent.node[i]['feats']) and (newsent.node[i]['cpostag'] == "VERB" or newsent.node[i]['cpostag'] == "AUX") and newsent.node[i]['form'][-2:] in twocharclitics and newsent.node[i]['form'] not in exclusion_list_verbs_es]
    return newsent


def apply_transform(sent,lang):
    newsent = copy.copy(sent)
    newsent = copy.copy(split_adpdet_contractions(newsent))
    if lang == "es":
        newsent = copy.copy(process_mwe_verbs(newsent))
    else:
        newsent = copy.copy(insert_multitoken_verbs_ca(newsent))


    return newsent


def main():
    parser = argparse.ArgumentParser(description="""Convert conllu to conll format""")
    #parser.add_argument('--input', help="conllu file", default='../..//UD_Spanish-AnCora/es_ancora-all.conllu')
    parser.add_argument('--input', help="conllu file", default='../..//UD_Catalan/ca-all.conllu')
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
        s = copy.copy(apply_transform(s,args.lang))
        #if not 'multi_tokens' in s.graph.keys():
        #    print(s.get_sentence_as_string())
        modif_treebank.append(s)
    cio.write_conll(modif_treebank,args.output,conllformat='conllu', print_fused_forms=True,print_comments=True)

if __name__ == "__main__":
    main()
