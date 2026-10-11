"""Quoted query lexer and parameterized OR-before-AND SQL compiler."""
import re

CATEGORIES = {'manga': '漫画', 'doujinshi': '同人誌', 'artist cg': 'アーティストCG', 'image set': '画像集', 'game cg': 'ゲームCG', 'anime': 'アニメ'}

def parse(query):
    groups, group, token = [], [], ''
    quoted = escaped = False
    def term():
        nonlocal token
        if not token:
            raise ValueError('Empty search expression')
        neg = token.startswith('-')
        text = token[1:] if neg else token
        if not text:
            raise ValueError('Missing value after NOT')
        field, value = text.split(':', 1) if ':' in text else ('', text)
        if not value.strip():
            raise ValueError('Missing search value')
        group.append((field.lower(), value.strip(), neg))
        token = ''
    chars = query.strip()
    pending_or = False
    for ch in chars:
        if escaped:
            if ch not in ('"', '\\'):
                raise ValueError('Only quote and backslash may be escaped')
            token += ch; escaped = False
        elif quoted and ch == '\\':
            escaped = True
        elif ch == '"':
            quoted = not quoted
        elif not quoted and ch in '()':
            raise ValueError('Parentheses are not supported')
        elif not quoted and ch == '/':
            term(); pending_or = True
        elif not quoted and ch.isspace():
            if token:
                term(); groups.append(group); group = []; pending_or = False
            elif pending_or:
                raise ValueError('OR alternatives must not be empty')
        else:
            token += ch; pending_or = False
    if quoted or escaped:
        raise ValueError('Unclosed quoted value')
    if pending_or:
        raise ValueError('Missing value after OR')
    if token:
        term()
    if group:
        groups.append(group)
    return groups

def compile_query(query, dimensions):
    params = []
    def p(value):
        params.append(value); return '?'
    def entity(value, kinds, gender=None, substring=False):
        compare = 'instr(fold(e.name), ?) > 0' if substring else 'fold(e.name) = ?'
        alias = 'instr(fold(a.name), ?) > 0' if substring else 'fold(a.name) = ?'
        params.extend(kinds)
        tail = ''
        if gender:
            tail = ' AND e.gender = ?'; params.append(gender)
        params.extend([value.casefold(), value.casefold()])
        return ('EXISTS(SELECT 1 FROM work_entities we JOIN entities e ON e.id=we.entity_id '
                'WHERE we.work_id=w.id AND e.owner=w.owner AND e.kind IN (' + ','.join('?' for _ in kinds) + ')' + tail +
                ' AND (' + compare + ' OR EXISTS(SELECT 1 FROM aliases a WHERE a.entity_id=e.id AND ' + alias + ')))')
    def expression(field, value):
        if field in ('title', 'review'):
            return f'instr(fold(w.{field}), {p(value.casefold())})>0'
        if not field:
            parts = [f'instr(fold(w.{col}), {p(value.casefold())})>0' for col in ('title', 'category', 'language')]
            cats = [k for k,v in CATEGORIES.items() if value.casefold() in v.casefold()]
            if cats:
                parts.append('w.category IN (' + ','.join(p(c) for c in cats) + ')')
            parts.append(entity(value, ['author','circle','tag','series','character'], substring=True))
            return '(' + ' OR '.join(parts) + ')'
        if field in ('author','circle','group','tag','female','male','neutral','series','character'):
            kind = 'circle' if field == 'group' else 'tag' if field in ('female','male','neutral') else field
            return entity(value, [kind], field if field in ('female','male','neutral') else None)
        if field in ('category','language'):
            if field == 'category':
                value = next((k for k,v in CATEGORIES.items() if v == value), value)
            return f'fold(w.{field})={p(value.casefold())}'
        if field == 'bought':
            if value.casefold() not in ('true','false','yes','no'):
                raise ValueError('Bought expects yes/no or true/false')
            return 'w.bought=' + p(int(value.casefold() in ('true','yes')))
        if field == 'pages' or re.fullmatch(r'rating[1-9]\d*', field):
            match = re.fullmatch(r'(>=|<=|>|<|=)?(\d+)', value)
            if not match:
                raise ValueError('Expected an integer comparison')
            op, num = match.group(1) or '=', int(match.group(2))
            if field == 'pages':
                return f'w.pages {op} {p(num)}'
            n = int(field[6:])
            if n not in dimensions:
                raise ValueError(f'Unknown rating dimension: {field}')
            if not 1 <= num <= dimensions[n]['maximum']:
                raise ValueError(f'{field} expects 1–{dimensions[n]["maximum"]}')
            return f'EXISTS(SELECT 1 FROM scores s WHERE s.work_id=w.id AND s.dimension_id={p(dimensions[n]["id"])} AND s.value {op} {p(num)})'
        raise ValueError('Unknown search field: ' + field + ('; use rating1, rating2, …' if field == 'rating' else ''))
    groups = []
    for group in parse(query):
        terms = []
        for field,value,neg in group:
            sql = expression(field,value)
            terms.append('NOT COALESCE((' + sql + '),0)' if neg else 'COALESCE((' + sql + '),0)')
        groups.append('(' + ' OR '.join(terms) + ')')
    return ' AND '.join(groups) or '1', params
