#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import codecs
import json
import unicodecsv as csv
import random

ap = argparse.ArgumentParser()
ap.add_argument("dataset", type=str, help="dataset to extend from")
ap.add_argument("db_csv", type=str, help="course database")
ap.add_argument("n_copy", type=int, help="make how many copies (with different slot values) for each")
ap.add_argument("out_file", type=str, help="output interface")
args = ap.parse_args()

# load courses from CSV
f_db = codecs.open(args.db_csv, "r")
reader = csv.DictReader(f_db)
courses = []
for row in reader:
    if row["instructor"] == "" or row["title"] == "":
        continue
    courses.append(row)

extend_data = [] # (intent, tokens, labels)
with codecs.open(args.dataset, "r", "utf-8") as f_in:
    lines = f_in.readlines()
    for i in range(0, len(lines), 3):
        intent = lines[i].strip()
        tokens = lines[i+1].strip().split(" ")
        labels = lines[i+2].strip().split(" ")
        if len(tokens) != len(labels):
            print tokens, labels
        for _ in range(args.n_copy):
            # draw a random course
            course = random.choice(courses)
            new_tokens = []
            new_labels = []
            for j in range(0, len(tokens)):
                if "I" in labels[j]:
                    continue
                t = tokens[j]
                if "B" in labels[j]:
                    slot = labels[j][2:]
                    if slot == "title":
                        t = course["title"]
                        if " " in t:
                            t = t.split(" ")[0]
                    elif slot == "instructor":
                        t = course["instructor"]
                        if " " in t:
                            t = t.replace(" ", "")

                new_tokens.append(t)
                new_labels.append(labels[j])
            extend_data.append( (intent, new_tokens, new_labels) )
                
        
random.shuffle(extend_data)
with codecs.open(args.out_file, "w", "utf-8") as f_out:
    for (intent, tokens, labels) in extend_data:
        f_out.write(intent + u"\n")
        f_out.write(u" ".join(tokens) + "\n")
        f_out.write(u" ".join(labels) + "\n")
