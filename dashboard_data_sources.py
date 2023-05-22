#!/usr/bin/env python3
import os
import json
import sys

def parse_chart_list(clist):
	charts = {}
	for c in clist:
		ch = c['chart']
		cname = ch['name']
		cid = ch['id']
		cprogram = ch['programText']
		clines = cprogram.split('\n')
		#print ('-chart', cid, ', name=', cname, ', lines=', len(clines))
		charts[cid] = {'name': cname, 'program': cprogram}
	return charts

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
				ptext += text[i]
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


def parse_dashboard_list(dlist, charts, prefix):
	for dli in dlist:
		d = dli['dashboard']
		clist = d['charts']
		prefix_plus = prefix + '\t' + d['name'] + '\t'
		for cli in clist:
			c = charts[cli['chartId']]
			#print(c)
			if len(c['program']) == 0:
				# just ignore empry programs - these are text/separators - no analytics
				continue
			data_expressions = None
			try:
				data_expressions = parse_data_expressions_from_program_text(c['program'])
				for dexp in data_expressions:
					#print(dexp)
					mchain = extract_method_chain(dexp)
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
							print('Syntax?:: ' + dexp + ' :: ' + c['program'], file=sys.stderr)
							mchain.append({'mname': 'publish', 'params': []})
							mlen = len(mchain)
						mraw = mchain[0]['params'][0]
						metric = mraw[1:len(mraw)-1]
						ftext = ""
						if len(mchain[0]['params']) > 1:
							for p in mchain[0]['params']:
								if len(p) > 7 and p[:7] == 'filter=':
									ftext = p[7:]
									break
						atext = []
						achain = mchain[1:len(mchain)-1]
						for method in achain:
							ptext = []
							for p in method['params']:
								ptext.append(p)
							atext.append(method['mname'] + '(' + ', '.join(ptext) + ')')
						print(prefix_plus + 'chart\t' + c['name'] + '\t' + metric + '\t' + ftext + '\t' + '.'.join(atext))
			except ValueError:
				# includes language constructs not parseable
				print("unparseable:: " + str(c['program']), file=sys.stderr)
	


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
		print(prefix + 'import_qualifier\t\t' +str(iqm) + '\t' + str(fexp) + '\t ') 
				
				

def parse_dashboard_group(text):
	jtext = json.loads(text)
	ge = jtext['groupExport']
	de = jtext['dashboardExports']
	cle = jtext['crossLinkExports']
	ce = jtext['chartExports']
	geg = ge['group']
	#print('Group:', geg['name'], ',', str(len(de)), 'dashboards,', str(len(ce)), 'charts')
	charts = parse_chart_list(ce)
	parse_dashboard_list(de, charts, geg['name'])
	parse_import_qualifiers(geg['importQualifiers'], geg['name'] + '\t\t')
	
	
group_dir = "group"

glist = os.listdir(group_dir)

print('group\tdashboard\tsource\titem\tmetric\tfilters\taggregations')

for g in glist:
	with open(group_dir + '/' + g, encoding='utf-8') as f:
		contents = f.read()
		parse_dashboard_group(contents)
