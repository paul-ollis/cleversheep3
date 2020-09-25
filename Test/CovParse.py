"""Parse support for the Cov module.

This is based largely on code from Ned Batchelder's coverage module. This
re-uses the code that analyses Python source code in order to determine which
lines are executable statments and which have been covered. The original
copyright for this code is shown below::

  # C. COPYRIGHT AND LICENCE
  #
  # Copyright 2001 Gareth Rees.  All rights reserved.
  # Copyright 2004-2008 Ned Batchelder.  All rights reserved.
  #
  # Redistribution and use in source and binary forms, with or without
  # modification, are permitted provided that the following conditions are
  # met:
  #
  # 1. Redistributions of source code must retain the above copyright
  #    notice, this list of conditions and the following disclaimer.
  #
  # 2. Redistributions in binary form must reproduce the above copyright
  #    notice, this list of conditions and the following disclaimer in the
  #    documentation and/or other materials provided with the
  #    distribution.
  #
  # THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
  # "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
  # LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
  # A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
  # HOLDERS AND CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
  # INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
  # BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
  # OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
  # ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
  # TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
  # USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
  # DAMAGE.

"""
from __future__ import print_function
__docformat__ = "restructuredtext"

import compiler
import compiler.visitor

class StatementFindingAstVisitor(compiler.visitor.ASTVisitor):
    """ A visitor for a parsed Abstract Syntax Tree which finds executable
    statements.

    """
    def __init__(self, statements, all_statements, excluded, suite_spots):
        compiler.visitor.ASTVisitor.__init__(self)
        self.statements = statements
        self.all_statements = all_statements
        self.excluded = excluded
        self.suite_spots = suite_spots
        self.excluding_suite = 0

    def doRecursive(self, node):
        self.recordNodeLine(node)
        for n in node.getChildNodes():
            self.dispatch(n)

    visitStmt = visitModule = doRecursive

    def doCode(self, node):
        if hasattr(node, 'decorators') and node.decorators:
            self.dispatch(node.decorators)
            self.recordAndDispatch(node.code)
        else:
            self.doSuite(node, node.code)

    visitFunction = visitClass = doCode

    def getFirstLine(self, node):
        # Find the first line in the tree node.
        lineno = node.lineno
        for n in node.getChildNodes():
            f = self.getFirstLine(n)
            if lineno and f:
                lineno = min(lineno, f)
            else:
                lineno = lineno or f
        return lineno

    def getLastLine(self, node):
        # Find the first line in the tree node.
        lineno = node.lineno
        for n in node.getChildNodes():
            lineno = max(lineno, self.getLastLine(n))
        return lineno

    def doStatement(self, node):
        self.recordLine(self.getFirstLine(node))

    visitAssert = visitAssign = visitAssTuple = visitDiscard = visitPrint = \
        visitPrintnl = visitRaise = visitSubscript = visitDecorators = \
        doStatement

    def recordNodeLine(self, node):
        return self.recordLine(node.lineno)

    def recordLine(self, lineno):
        # Returns a bool, whether the line is included or excluded.
        # print("REC", lineno)
        if lineno:
            self.all_statements[lineno] = 1

            # Multi-line tests introducing suites have to get charged to their
            # keyword.
            if lineno in self.suite_spots:
                lineno = self.suite_spots[lineno][0]
            # If we're inside an exluded suite, record that this line was
            # excluded.
            if self.excluding_suite:
                # print("EXCLUDE", lineno, self.excluding_suite)
                self.excluded[lineno] = self.excluding_suite
                return self.excluding_suite

            # If this line is excluded, or suite_spots maps this line to
            # another line that is excluded, then we're excluded.
            elif self.excluded.has_key(lineno):
                return self.excluded[lineno]
            elif self.suite_spots.has_key(lineno) and \
                 self.excluded.has_key(self.suite_spots[lineno][1]):
                return self.excluded[self.suite_spots[lineno][1]]
            # Otherwise, this is an executable line.
            else:
                self.statements[lineno] = 1
                return 1

        return 0

    default = recordNodeLine

    def recordAndDispatch(self, node):
        self.recordNodeLine(node)
        self.dispatch(node)

    def doSuite(self, intro, body, exclude=0, qq=0):
        exsuite = self.excluding_suite
        exclTag = None
        # if not exclude and intro:
        if intro:
            # if qq:
            #     print("SUITE", intro.lineno, body.__class__, len(body.nodes))
            exclTag = self.recordNodeLine(intro)
        if exclude:
            self.excluding_suite = exclude
        elif exclTag not in [None, 1, 0]:
            self.excluding_suite = exclTag
        # if qq or self.excluding_suite == 1:
        #     print("EXCL-1", body.lineno, self.excluding_suite, exsuite, exclude, exclTag)
        self.recordAndDispatch(body)
        self.excluding_suite = exsuite
        # if qq:
        #     print("EXCL-2", body.lineno, self.excluding_suite, exsuite)

    def doPlainWordSuite(self, prevsuite, suite):
        # Finding the exclude lines for else's is tricky, because they aren't
        # present in the compiler parse tree.  Look at the previous suite,
        # and find its last line.  If any line between there and the else's
        # first line are excluded, then we exclude the else.
        lastprev = self.getLastLine(prevsuite)
        firstelse = self.getFirstLine(suite)
        for l in range(lastprev+1, firstelse):
            if self.suite_spots.has_key(l):
                self.doSuite(None, suite, exclude=self.excluded.get(l, 0))
                break
        else:
            self.doSuite(None, suite)

    def doElse(self, prevsuite, node):
        if node.else_:
            self.doPlainWordSuite(prevsuite, node.else_)

    def visitFor(self, node):
        self.doSuite(node, node.body)
        self.doElse(node.body, node)

    def visitIf(self, node):
        # The first test has to be handled separately from the rest.
        # The first test is credited to the line with the "if", but the others
        # are credited to the line with the test for the elif.
        exsuite = self.excluding_suite
        exclTag = self.recordNodeLine(node)
        if exclTag not in [None, 1, 0]:
            self.excluding_suite = exclTag
        # print("IF", node.lineno, self.excluding_suite)

        # print("EXCL-XX", node.lineno, self.excluding_suite, exsuite)
        self.doSuite(node, node.tests[0][1])
        for t, n in node.tests[1:]:
            self.doSuite(t, n, qq=1)
        # print("EXCL-YY", node.lineno, self.excluding_suite, exsuite)
        self.doElse(node.tests[-1][1], node)

        # print("EXCL-ZZ", node.lineno, self.excluding_suite, exsuite)
        self.excluding_suite = exsuite

    def visitWhile(self, node):
        self.doSuite(node, node.body)
        self.doElse(node.body, node)

    def visitTryExcept(self, node):
        self.doSuite(node, node.body)
        for i in range(len(node.handlers)):
            a, b, h = node.handlers[i]
            if not a:
                # It's a plain "except:".  Find the previous suite.
                if i > 0:
                    prev = node.handlers[i-1][2]
                else:
                    prev = node.body
                self.doPlainWordSuite(prev, h)
            else:
                self.doSuite(a, h)
        self.doElse(node.handlers[-1][2], node)

    def visitTryFinally(self, node):
        self.doSuite(node, node.body)
        self.doPlainWordSuite(node.body, node.final)

    def visitGlobal(self, node):
        # "global" statements don't execute like others (they don't call the
        # trace function), so don't record their line numbers.
        pass


def get_suite_spots(tree, spots):
    """ Analyze a parse tree to find suite introducers which span a number
    of lines.

    """
    import symbol, token
    for i in range(1, len(tree)):
        if type(tree[i]) == type(()):
            if tree[i][0] == symbol.suite:
                # Found a suite, look back for the colon and keyword.
                lineno_colon = lineno_word = None
                for j in range(i-1, 0, -1):
                    if tree[j][0] == token.COLON:
                        lineno_colon = tree[j][2]
                    elif tree[j][0] == token.NAME:
                        if tree[j][1] == 'elif':
                            # Find the line number of the first non-terminal
                            # after the keyword.
                            t = tree[j+1]
                            while t and token.ISNONTERMINAL(t[0]):
                                t = t[1]
                            if t:
                                lineno_word = t[2]
                        else:
                            lineno_word = tree[j][2]
                        break
                    elif tree[j][0] == symbol.except_clause:
                        # "except" clauses look like:
                        # ('except_clause', ('NAME', 'except', lineno), ...)
                        if tree[j][1][0] == token.NAME:
                            lineno_word = tree[j][1][2]
                            break
                if lineno_colon and lineno_word:
                    # Found colon and keyword, mark all the lines
                    # between the two with the two line numbers.
                    for l in range(lineno_word, lineno_colon+1):
                        spots[l] = (lineno_word, lineno_colon)
            get_suite_spots(tree[i], spots)



class SrcInfo:
    pass


class ExclusionError(Exception):
    pass


def find_executable_statements(text, excludeCheck=lambda l:False):
    pure_excluded = {}
    excluded = {}
    special_lines = {}
    suite_spots = {}
    srcLines = [l.rstrip() for l in text.splitlines()]
    for i, line in enumerate(srcLines):
        v = None
        try:
            v = excludeCheck(line)
        except ExclusionError as exc:
            exc.lNum = i + 1
            raise exc
        if v:
            excluded[i+1] = v

    import parser
    tree = parser.suite(text+'\n\n').totuple(1)
    get_suite_spots(tree, suite_spots)

    # Use the compiler module to parse the text and find the executable
    # statements.  We add newlines to be impervious to final partial lines.
    statements = {}
    all_statements = {}
    ast = compiler.parse(text+'\n\n')
    visitor = StatementFindingAstVisitor(statements, all_statements,
            excluded, suite_spots)
    compiler.walk(ast, visitor, walker=visitor)

    lines = statements.keys()
    lines.sort()
    excluded_lines = excluded.keys()
    excluded_lines.sort()

    info = []
    for lidx in range(len(srcLines)):
        if (lidx + 1) not in all_statements:
            # Not an executable line
            info.append(None)
        elif (lidx + 1) in excluded_lines:
            info.append(excluded[lidx + 1])
        else:
            info.append(1)

    stats = SrcInfo()
    stats.info = info
    stats.specialLines = special_lines
    return stats
