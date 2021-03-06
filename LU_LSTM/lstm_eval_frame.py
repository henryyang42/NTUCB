#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import codecs
import numpy as np
from keras.models import Model, Sequential, load_model
from keras.layers import Dense, Activation, Dropout, Embedding, TimeDistributed, LSTM
from keras.layers.core import Dropout
from keras.layers.wrappers import Bidirectional
from keras.layers import Input, merge
from keras.optimizers import *
from keras.preprocessing import sequence
from keras.utils import np_utils
import json
import re
from LSTM_util import *

#arguments
ap = argparse.ArgumentParser()
ap.add_argument("test_dataset", help="segmented test dataset, with intent & label")
ap.add_argument("model", type=str, help="Keras model to load")
ap.add_argument("vocab", type=str, help="idx2word table for word, slot, intent (in JSON format)")
args = ap.parse_args()

# load vocab
obj = json.load(open(args.vocab, "r"))
idx2label = obj["slot_vocab"]
idx2intent = obj["intent_vocab"]
word2idx = {}
for i, w in enumerate(obj["word_vocab"]):
    word2idx[w] = i

# load model
model = load_model(args.model)
seq_len =  model.input_layers[0].batch_input_shape[1]
#print "== load model done =="

# prediction on test data
with codecs.open(args.test_dataset, "r", "utf-8") as f_test:
    lines = f_test.readlines()
    seq_list = []
    len_list = []
    tokens_list = []
    true_intent_list = []
    true_labels_list = []
    n_data = int(len(lines) / 3)
    for i in range(0, len(lines), 3):
        intent = lines[i].strip()
        tokens = lines[i+1].strip().split(" ")
        labels = lines[i+2].strip().split(" ")
        
        tokens_list.append(tokens)

        true_intent_list.append(intent)
        true_labels_list.append(labels)
    
        # pad sequence
        idx_seq = seq_word2idx(tokens, word2idx)
        if len(idx_seq) < seq_len:
            pad_idx_seq = [0]*(seq_len-len(idx_seq)) + idx_seq
        elif len(idx_seq) > seq_len:
            pad_idx_seq = idx_seq[-seq_len : ]
        else:
            pad_idx_seq = idx_seq
        len_list.append(len(idx_seq))
        seq_list.append(pad_idx_seq)

# predict
pred_label_vec_list, pred_intent_vec_list = model.predict(np.array(seq_list))

# compare result & answer
acc = 0.0
slot_acc = 0.0
for i in range(0, n_data):
    intent_idx = pred_intent_vec_list[i].argmax()
    pred_intent = idx2intent[intent_idx]

    slot_idx_seq = pred_label_vec_list[i].argmax(axis=-1)
    pred_labels = seq_idx2word(slot_idx_seq[-len_list[i] : ], idx2label)
    for j, l in enumerate(pred_labels):
        if l == '#':
            pred_labels[j] = 'O'
    assert len(pred_labels) == len(true_labels_list[i])

    if pred_labels == true_labels_list[i]:
        slot_acc += 1
        if pred_intent == true_intent_list[i]:
            acc += 1
    
acc /= n_data
slot_acc /= n_data
print ("Frame Accuracy:", acc)
print ("Frame Accuracy except intent:", slot_acc)
