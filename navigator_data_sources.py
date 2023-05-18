#!/usr/bin/env python3

import os
import json
import sys

def try_or_none(jdict, tag):
	value = None
	try:
		value = jdict[tag]
	except KeyError:
		value = None
	return value


def extract_next_method_call(text):
	i = 0
	mname = ''
	while text[i] != '(':
		mname += text[i]
		i += 1
	# count initial paren
	i += 1
	pcount = 1
	quoted = False
	listed = False
	qchar = ''
	lchar = ''
	plist = []
	ptext = ''
	while pcount > 0:
		if quoted:
			if text[i] == qchar:
				quoted = False
				qchar = ''
			ptext += text[i]
		elif listed:
			if text[i] == ']':
				listed = False
				lchar = ''
			ptext += text[i]
		elif pcount > 1:
			if text[i] == '(':
				pcount += 1
			elif text[i] == ')':
				pcount -= 1
			ptext += text[i]
		else:
			if text[i] in ['"', "'"]:
				quoted = True
				qchar = text[i]
				ptext += text[i]
			elif text[i] == '[':
				listed = True
				lchar = text[i]
				ptext += text[i]
			elif text[i] == ',':
				plist.append(ptext.strip())
				ptext = ''
			elif text[i] == '(':
				pcount += 1
			elif text[i] == ')':
				pcount -= 1
			else:
				ptext += text[i]
		i += 1
	if len(ptext) > 0:
		plist.append(ptext.strip())
	return (i, {'mname': mname, 'params': plist})
			
	

def extract_method_chain(text):
	chain = []
	remaining = text.strip()[:]
	while len(remaining) > 0:
		tok = extract_next_method_call(remaining)
		plen = tok[0]
		assert(plen > 0)
		assert(len(tok) == 2)
		chain.append(tok[1])
		if plen < len(remaining):
			remaining = remaining[plen+1:]
		else:
			remaining = ''
	return chain
			


def parse_data_expressions_from_program_text(program):
	# assume program is a collection of single-line assignments
	lines = program.split('\n')
	data_exps = []
	for line in lines:
		if len(line.strip()) == 0:
			continue
		assign = line.split('=',1)
		#print(assign)
		#print(len(assign))
		if len(assign) == 1:
			#print('UNPARSEABLE:' + line)
			raise ValueError("Unparseable program")
		assert(len(assign) == 2)
		dataexp = assign[1].split('data')
		if len(dataexp) < 2:
			continue
		else:
			data_exps.append(assign[1].strip())
	return data_exps


def parse_color_by_metrics(mlist, prefix):
	prefix_plus = prefix
	for m in mlist:
		mjob = try_or_none(m, 'job')
		if mjob is not None:
			template = try_or_none(mjob, 'template')
			#print(template)
			data_expressions = parse_data_expressions_from_program_text(template)
			#print(data_expressions)
			
			for dexp in data_expressions:
				#print(dexp)
				try:
					mchain = extract_method_chain(dexp)
				except IndexError:
					print("SYNTAX ERROR:: ", template, file=sys.stderr)
					continue
				#print(mchain)
				#print(len(mchain))
				#assert(mchain[0]['mname'] == 'data')
				if mchain[0]['mname'] != 'data':
					for method in mchain:
						assert(method['mname'] != 'data')
					#print('NODATA:: ' + dexp)
				else:
					mlen = len(mchain)
					#assert(mchain[mlen-1]['mname'] == 'publish')
					if mchain[mlen-1]['mname'] != 'publish':
						#print('Syntax?:: ' + dexp + ' :: ' + template, file=sys.stderr)
						mchain.append({'mname': 'publish', 'params': []})
						mlen = len(mchain)
					mraw = mchain[0]['params'][0]
					#print(mraw)
					if mraw[-11:] == '{{#filter}}':
						mraw = mraw[:len(mraw)-11]
					#print(mraw)
					metric = mraw[1:len(mraw)-1]
					ftext = ""
					if len(mchain[0]['params']) > 1:
						for p in mchain[0]['params']:
							if len(p) > 7 and p[:7] == 'filter=':
								ftext = p[7:]
								break
					#print(ftext)
					atext = []
					achain = mchain[1:len(mchain)-1]
					for method in achain:
						ptext = []
						for p in method['params']:
							ptext.append(p)
						atext.append(method['mname'] + '(' + ', '.join(ptext) + ')')
					print(prefix_plus + 'color by\t' + metric + '\t' + "" + '\t' + '.'.join(atext))


def parse_import_qualifiers(iqlist, prefix):
	for iq in iqlist:
		iqm = iq['metric']
		iqflist = iq['filters']
		fexp = ''
		first = True
		for iqf in iqflist:
			if first:
				first = False
			else:
				fexp += ' AND '
			fexp += '"' + iqf['property'] + '"'
			iqvlist = iqf['values']
			if len(iqvlist) > 1:
				if iqf['not']:
					fexp += ' not in ["'
				else:
					fexp += ' in ["'
				fexp += '", "'.join(iqvlist)
				fexp += '"]'
			else:
				if iqf['not']:
					fexp += ' != '
				else:
					fexp += ' == '
				if len(iqvlist) > 0:
					fexp += '"' + iqvlist[0]  + '"'
				else:
					fexp += '"*"'
		print(prefix + 'import_qualifier\t' +str(iqm) + '\t' + str(fexp) + '\t ') 	


def parse_navigator(text):
	jtext = json.loads(text)
	ne = jtext['navigatorExport']
	nen = ne['navigator']
	nname = try_or_none(nen, 'name')
	ncatgrp = try_or_none(nen, 'navigatorCategoryGroupDisplayName')
	ncategory = try_or_none(nen, 'navigatorCategoryDisplayName')
	#print(ncatgrp, ncategory, nname)
	iqf = try_or_none(nen, 'importQualifiers')
	if iqf is not None:
		parse_import_qualifiers(iqf, str(ncatgrp) + '\t' + str(ncategory) + '\t' + str(nname) + '\t')
	uim = try_or_none(nen, 'uiModel')
	metrics_list = try_or_none(uim, 'metrics')
	if metrics_list is not None:
		parse_color_by_metrics(metrics_list, str(ncatgrp) + '\t' + str(ncategory) + '\t' + str(nname) + '\t')


navigator_dir = 'navigators'

print('category group\tcategory\tnavigator\tsource\tmetric\tfilters\taggregations')

for root, subdirs, files in os.walk(navigator_dir):
	for filename in files:
		fpath = os.path.join(root, filename)
		ext = fpath.split(".")[-1:][0]
		if ext == 'json':
			#print(filename, fpath)
			with open(fpath, encoding='utf-8') as f:
				contents = f.read()
				parse_navigator(contents)
