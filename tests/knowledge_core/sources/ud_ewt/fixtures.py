from __future__ import annotations


SAMPLE_CONLLU = """# sent_id = s1
# newdoc id = doc1
# text = They've been seen by John.
1-2	They've	_	_	_	_	_	_	_	_
1	They	they	PRON	PRP	Case=Nom|Number=Plur|Person=3	4	nsubj:pass	4:nsubj:pass	_
2	've	have	AUX	VBP	Mood=Ind|Tense=Pres|VerbForm=Fin	4	aux	4:aux	_
3	been	be	AUX	VBN	Tense=Past|VerbForm=Part	4	aux:pass	4:aux:pass	_
4	seen	see	VERB	VBN	Tense=Past|VerbForm=Part	0	root	0:root	_
5	by	by	ADP	IN	_	6	case	6:case	_
6	John	John	PROPN	NNP	Number=Sing	4	obl:agent	4:obl:agent	SpaceAfter=No
7	.	.	PUNCT	.	_	4	punct	4:punct	_

# sent_id = s2
# text = I go.
1	I	I	PRON	PRP	Case=Nom|Number=Sing|Person=1	2	nsubj	2:nsubj	_
2	go	go	VERB	VBP	Mood=Ind|Tense=Pres|VerbForm=Fin	0	root	0:root	_
2.1	quickly	quickly	ADV	RB	_	_	_	2:advmod	Empty=Yes
3	.	.	PUNCT	.	_	2	punct	2:punct	_

# sent_id = s3
# text = The cat can sleep.
1	The	the	DET	DT	Definite=Def|PronType=Art	2	det	2:det	_
2	cat	cat	NOUN	NN	Number=Sing	4	nsubj	4:nsubj	_
3	can	can	AUX	MD	VerbForm=Fin	4	aux	4:aux	_
4	sleep	sleep	VERB	VB	VerbForm=Inf	0	root	0:root	SpaceAfter=No
5	.	.	PUNCT	.	_	4	punct	4:punct	_

"""

