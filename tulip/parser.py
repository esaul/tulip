from tulip.syntax import *
from tulip.parser_gen import string, generate, char_range, one_of, none_of, seq, alt, Box

class ASTBox(Box.Base):
    def __init__(self, syntax):
        assert isinstance(syntax, Syntax)
        self.syntax = syntax

    def get_ast(self):
        return self.syntax

    def dump(self):
        return u"<Box.AST (%s)>" % self.syntax.dump()

whitespace = one_of(u" \t").many()
nl = alt(string(u"\n"), string(u"\r\n"))
comment = seq(string(u'#'), none_of(u"\n").many(), nl)
LINES = seq(alt(nl, comment, string(u";")).many(), whitespace)

lexeme = lambda p: p.skip(whitespace)
lineme = lambda p: p.skip(LINES)

digit = char_range(u'0', u'9')
ident_start = char_range(u'a', u'z')
ident_ch = alt(char_range(u'a', u'z'), one_of(u'-_'), digit)

@generate
def ident(gen):
    start = gen.parse(ident_start).get_string()
    rest = gen.parse(ident_ch.scan()).get_string()
    return Box.String(start + rest)

NUMBER = lexeme(digit.scan1()).desc(u'number')
IDENT =  lexeme(ident).desc(u'ident')
RANGLE = lineme(string('>'))
LPAREN = lineme(string('('))
RPAREN = lexeme(string(')'))
LBRACE = lineme(string('['))
RBRACE = lineme(string(']'))
DOLLAR = lexeme(string('$'))
TAGGED = lexeme(string('.').then(IDENT))
CHECK  = lexeme(string('%').then(IDENT))
RARROW = lineme(string('=>'))
PLUS   = lexeme(string('+'))
EQUAL  = lexeme(string('='))

MODULE = lexeme(string('@module'))

@generate('atom')
def atom(gen):
    return gen.parse(alt(var, number, paren, lam, tag, autovar))

@generate('apply')
def apply(gen):
    atoms = gen.parse(atom.many1()).get_list()
    if len(atoms) == 1:
        return atoms[0]
    else:
        return ASTBox(Apply([a.get_ast() for a in atoms]))

@generate('chain')
def chain(gen):
    first = gen.parse(apply)
    gen.parse(LINES)
    rest = gen.parse(RANGLE.then(apply).many()).get_list()
    gen.parse(LINES)

    if len(rest) == 0:
        return first

    chain_size = len(rest) + 1
    out = [None] * chain_size
    out[0] = first.get_ast()
    for i in range(0, chain_size-1):
        out[i+1] = rest[i].get_ast()

    return ASTBox(Chain(out))

@generate
def definition(gen):
    gen.parse(PLUS)
    name = gen.parse(IDENT).get_string()
    args = [a.get_ast() for a in gen.parse(pattern.many()).get_list()]
    gen.parse(EQUAL)
    body = gen.parse(expr).get_ast()
    return ASTBox(Definition(sym(name), args, body))

@generate
def expr(gen):
    clauses = [c.get_ast() for c in gen.parse(definition.many()).get_list()]
    body = gen.parse(chain).get_ast()

    if len(clauses) == 0:
        return ASTBox(body)
    else:
        return ASTBox(Let(clauses, body))

@generate('pattern')
def pattern(gen):
    return gen.parse(alt(var_pattern, tag_pattern, named_pattern, paren_pattern))

paren_pattern = LPAREN.then(pattern).skip(RPAREN)
var_pattern = IDENT.map(lambda s: ASTBox(VarPat(sym(s.get_string()))))

@generate
def tag_pattern(gen):
    tag = gen.parse(TAGGED).get_string()
    args = gen.parse(pattern.many()).get_list()
    pats = [p.get_ast() for p in args]
    return ASTBox(TagPat(sym(tag), pats))

named_pattern = CHECK.map(lambda s: ASTBox(NamedPat(sym(s.get_string()))))


var = IDENT.map(lambda s: ASTBox(Var(sym(s.get_string()))))
number = NUMBER.map(lambda s: ASTBox(Int(int(s.get_string()))))
paren = LPAREN.then(expr).skip(RPAREN)
autovar = DOLLAR.map(lambda _: ASTBox(Autovar()))
tag = TAGGED.map(lambda s: ASTBox(Tag(sym(s.get_string()))))
lam_start = LBRACE

def _lam_map(args):
    pat, body = args.get_list()
    clause = Lam.Clause(pat.get_ast(), body.get_ast())
    return ASTBox(Lam([clause]))

# TODO: multiple clauses
@generate
def lam_clause(gen):
    pat = gen.parse(pattern).get_ast()
    gen.parse(LINES)
    gen.parse(RARROW)
    body = gen.parse(expr).get_ast()
    return ASTBox(Lam.Clause(pat, body))

@generate
def lam_end(gen):
    clauses = gen.parse(lam_clause.many()).get_list()
    clauses = [c.get_ast() for c in clauses]
    gen.parse(RBRACE)

    return ASTBox(Lam(clauses))

autolam_end = expr.skip(RBRACE).map(lambda c: ASTBox(Autolam(c.get_ast())))

lam = lam_start.then(alt(lam_end.backtracking(), autolam_end))

@generate
def module_item(gen):
    return gen.parse(alt(definition, module_decl))

@generate
def module_decl(gen):
    gen.parse(MODULE)
    name = sym(gen.parse(IDENT).get_string())
    pats = [p.get_ast() for p in gen.parse(pattern.many()).get_list()]
    gen.parse(EQUAL)
    gen.parse(LBRACE)
    items = [i.get_ast() for i in gen.parse(module_item.many()).get_list()]
    gen.parse(RBRACE)
    return ASTBox(Module(name, pats, items))

@generate
def bare_module(gen):
    gen.parse(MODULE)
    name = sym(gen.parse(IDENT).get_string())
    pats = [p.get_ast() for p in gen.parse(pattern.many()).get_list()]
    gen.parse(LINES)
    items = [i.get_ast() for i in gen.parse(module_item.many()).get_list()]
    return ASTBox(Module(name, pats, items))

expr_parser = LINES.then(expr)
module_parser = LINES.then(bare_module)
