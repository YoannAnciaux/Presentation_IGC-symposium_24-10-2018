#!/usr/bin/python3

# read layers to export from `.anim` or print them successively in order
#
# `.anim` file:
#       suffix_of_the_animation: ignored comment
#       layerID
#       layerID layerID2 for/the second/slide
#       layers           for/the third
#       + syntaxFor appendingTo previousLayer
#       - syntaxFor previousLayer + removalThenAppendNew
#       + syntax/{for factorizing - accross paths}
#       and/even/{accross
#       + lines
#       - cool}
#
#       suffix_for_another_animation: the column is important
#       1
#       1 3 4 # comment up to the end of the line
#       # comment, line ignored
#       # the next line is a blank slide
#       * # this means blank slide
#       # the next blank line is.. just ignored
#
#       # and here it starts again
#       1 4 5
#
# if none, just display them successively in order
# of course, layer ids must be unique :)

import sys                                 # to retrieve command arguments
import __main__                            # to check interactivity
from subprocess import Popen, PIPE, STDOUT # to execute system commands
from os.path import basename, isfile
from xml.dom import minidom                # to parse xml
import codecs                              # to write xml
import re                                  # for processing /{} constructs
def popen(cmd):
    """send a command and get a Popen object in return :)
    """
    return Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE,
          stderr=PIPE, close_fds=True)
def popres(cmd):
    """return decoded stdout or raise an error if stderr has content
    """
    pop = popen(cmd)
    errors = pop.stderr.read()
    if errors:
        print("Popen got errors:")
        print(errors.decode())
        raise Exception()
    else:
        return pop.stdout.read().decode()
def interactive():
    """are we running an interactive session?
    """
    return not hasattr(__main__, '__file__')
def base(filename):
    """just strip the extension off
    """
    return filename.split('.', 1)[0]
def log(string=''):
    """log if needed (skipped for parallel execution)
    """
    if logging:
        print(string)

# .svg file to animate
if interactive():
    # for tests and debugging
    sources = ["uml.svg"]
    logging = True
else:
    sources=sys.argv[1:]
    if not sources:
        print("no .svg file given.")
        exit(1)
    logging = False

# Parse and edit .svg (xml) files with minidom:
# `g` refers to a minidom node
# `node` refers to our custom Node class
is_layer = lambda g: g.attributes \
                   and "inkscape:label" in g.attributes.keys()
get_name = lambda g: g.attributes["inkscape:label"].value
def setup(g):
    """if we know it is a layer, add missing attributes to it
    """
    if not g.hasAttribute('style'):
        g.setAttribute('style', 'display:none')
    return g
def switch(g, on=True):
    """hide or show a layer minidom node
    """
    value = "display:" + ("inline" if on else "none")
    attrn = 'style'
    g.setAttribute('style', value)
is_on = lambda g: g.attributes["style"].value == "display:inline"
def get_kids(g):
    """iterate over minidom kids of minidom node
    """
    for kid in g.childNodes:
        if is_layer(kid):
            setup(kid)
            yield kid
def get_parent(g):
    """return the parent *layer* or None if root
    """
    res = g.parentNode
    if is_layer(res):
        return setup(res)
    return None
def get_root_parent(g):
    """successive call to get_parent until a root is found
    """
    while True:
        parent = get_parent(g)
        if parent:
            g = parent
        else:
            return g

class Node(object):
    """basic arborescent node, linking the name and the visible state
    to the `minidom` node, holding kids
    """

    def __init__(self, g, parent):
        """g: minidom node, None for root node
        parent: parent Node
        """
        self.parent = parent
        self.g = g
        # kids are mapped with their names
        kids = {}
        for k in get_kids(g):
            kids[get_name(k)] = Node(k, self)
        self.kids = kids

    def add_kid(self, node):
        self.kids[node.name] = node
        node.parent = self

    @property
    def name(self):
        return get_name(self.g)

    @property
    def visible(self):
        try:
            return is_on(self.g)
        except KeyError as e:
            # TEMP: I havent understood this problem yet
            print("{} not visible?".format(self.g))

    @visible.setter
    def visible(self, value):
        switch(self.g, value)

    def display(self, prefix=''):
        """recursive visualization of the node, kids and visibility
        """
        res = "{}{}: {}\n".format(prefix, self.name,
                                  'X' if self.visible else '')
        for k in self.kids.values():
            res += k.display(prefix=prefix + 4 * ' ')
        return res

    def __repr__(self):
        return self.display()

    def to_kid(self, path):
        """Iterate while navigating to a kid. Receive an arborescent
        path of/this/form:
        """
        yield self
        if '/' in path:
            first, next = path.split('/', 1)
            yield from self.kids[first].to_kid(next)
        else:
            yield self.kids[path]

    def get_kid(self, path):
        """Receive an arborescent path of/this/form
        to retrieve the corresponding kid:
        """
        # just navigate to the last one:
        for node in self.to_kid(path):
            pass
        return node

    @property
    def leaves(self):
        """Iterates over all leaves nodes
        """
        if self.kids:
            for kid in self.kids.values():
                yield from kid.leaves()
        else:
            yield self

    @property
    def lineage(self):
        """Iterates back to a root node.
        """
        if not isinstance(self, Forest):
            yield self
            yield from self.parent.lineage

    @property
    def path(self):
        """build the path to access to this node, iterating backwards:
        """
        res = []
        for parent in self.lineage:
            res.append(parent.name)
        return '/'.join(reversed(res))

    def __iter__(self):
        """Iterate recursively over all nodes
        """
        if not isinstance(self, Forest):
            yield self
        for kid in self.kids.values():
            yield from kid.__iter__()

class Forest(Node):
    """Extension: the forest node has no minidom node and no name, but
    kids. Every node has at least one forest parent.
    The forest holds a whole `svg` minidom image. Which should be
    independent from other forest images.
    """

    def __init__(self, file):
        """Initiate the forest with a `.svg` file
        """
        self.svg = minidom.parse(open(file))
        self.kids = {}
        # strategy since the order is unknown: climb up to a root node,
        # if it is unknown, recursively add all its kids to the forest:
        for g in self.svg.getElementsByTagName('g'):
            if is_layer(g):
                root = get_root_parent(g)
                name = get_name(root)
                if name not in self.kids:
                    self.add_kid(Node(root, self))

    @property
    def name(self):
        return '/'

    @property
    def visible(self):
        """ always visible
        """
        return True

    @visible.setter
    def visible(self, value):
        """ dummy
        """
        pass

    def switch_on(self, path):
        """Set visibility to the given node AND all its lineage.
        """
        for node in self.to_kid(path):
            node.visible = True

    def switch_off(self, path):
        """Unset visibility to the given node only
        """
        node = self.get_kid(path)
        node.visible = False

    def write(self, file):
        """export this version of the .svg image to a new .svg file.
        """
        export = self.svg.toxml()
        codecs.open(file, "w", encoding="utf8").write(export)

    @property
    def summary(self):
        """Summarize the state of the forest with a list of all nodes
        and their visible state, so that it may be restored later:
        [(node, True),..] for a visible node, etc.
        """
        res = []
        for node in self:
            res.append((node, node.visible))
        return res

    def restore(self, summary):
        """Restore the state of the forest based on the summary:
        """
        for node, state in summary:
            node.visible = state

    def clear(self):
        """Set all nodes to invisible
        """
        for node in self:
            node.visible = False

def animate(slides, anim_suffix=''):
    """perform the actual animation job by writing temporary .svg files
    contributes to filling up `temp_files`, reads from global `source`,
    `script`, `forest`, etc.
    """

    suffix = ('-' if anim_suffix else '') + anim_suffix
    result_file = base(source) + suffix + '.pdf'

    print("  {} to {}".format(source, result_file))

    log("Animating " + anim_suffix)

    log("Extracting correct layers to %s-part-*.svg.." \
            % (base(source) + suffix))
    # Write svg files successively
    temp_svg = []
    for i, sl in enumerate(slides):
        output = source.replace('.', '-part-%02d.' % (i + 1))
        temp_svg.append(output)
        forest.restore(sl)
        forest.write(output)
    temp_files.update(set(temp_svg))

    log("Converting to .pdf..")
    commands = []
    temp_pdf = []
    for file in temp_svg:
        output = base(file) + suffix + '.pdf'
        temp_pdf.append(output)
        command = 'inkscape -f {} -A {} &\n'.format(file, output)
        commands.append(command)
    # parallel execute then wait.
    command = ''.join(commands) + 'wait'
    out = popres(command)
    temp_files.update(set(temp_pdf))

    log("Merging result..")
    command = 'pdftk {} cat output {} '.format(' '.join(temp_pdf), result_file)
    out = popres(command)
    log()

# iterate on given files, produce one .pdf for each of them
log()
while sources:
    source = sources.pop()

    # gather here all temporary files that'll need to be cleaned up
    temp_files = set()

    log("Analysing %s.." % source)

    # Parse the source .svg file to get a forest image of nested layers
    # visibility.
    forest = Forest(source)
    forest.visible

    # check whether a `.anim` is available:
    anim_file = base(source) + '.anim'
    # encode each slide as successive summaries of the forest
    slides = []
    if isfile(anim_file):

        # Yupe it is! parse it to get the layers in the right order:
        with open(anim_file) as f:
            # get whole content of the file
            content = f.read()
        # First get rid of the comments:
        content = re.sub(r'[ \t]*#.*', '', content, re.MULTILINE)
        # Empty lines will be ignored during the process

        # Distribute the "factor/{term + - \n term}" patterns into
        #                "factor/term + - \n factor/term"
        # Replace the most inner ones with regexes until there are no
        # more.
        one_at_least = False
        while True:
            match = re.search('([\w/]+/){([^{}]+)}', content, re.S)
            if match:
                one_at_least = True
                head, inside = match.groups()
                # distribute head over paths inside
                dis = re.sub('([\w/]+)', head + '\g<1>', inside)
                content = content[:match.start()] + dis + content[match.end():]
            else:
                break
        if one_at_least:
            del dis, head, inside, match
        del one_at_least
        # Now this may be analysed line by line (last line empty)
        content = content.split('\n')[:-2]

        # Prepare the first animation:
        anim_suffix = content.pop(0).split(':', 1)[0]
        operators = {'+', '-'}
        def check_node(path):
            """Check that the node does exist in the forest or raise an
            error
            """
            try:
                forest.get_kid(path)
            except KeyError as e:
                raise Exception("The id '{}' is not in {} layers!" \
                        .format(e.args[0], source))
        def check_operator(string):
            """We are expecting an operator: check that this is one:
            """
            if string not in operators:
                raise Exception("A relative line must start with {}, not {}." \
                        .format(" or ".join(operators), string))
        while content:
            line = content.pop(0)
            if not re.search('\S', line): # skip blank lines
                continue
            if ':' in line:
                # ah, new animation!
                animate(slides, anim_suffix)
                # and prepare the next animation!
                anim_suffix = line.split(':', 1)[0]
                slides = []
                continue
            # retrieve ordered tokens on the line:
            tokens = line.split()
            # There may be a star as first token: it means clear up!
            if tokens[0] == '*':
                forest.clear()
                tokens.pop(0)
                # if this was the only token, then we're done with this
                # line.
                if not tokens:
                    slides.append(forest.summary)
                    continue

            from_scratch = not any(op in tokens for op in operators)
            if from_scratch:
                # Then all tokens are visible paths all other nodes will
                # be hidden
                for path in tokens:
                    check_node(path)
                # switch everyone off
                forest.clear()
                # then turn on visible ones:
                for path in tokens:
                    forest.switch_on(path)
            else:
                # then this layer is defined relatively to the last one:
                # read the tokens to build the currently visible ones:
                next = tokens.pop(0)
                check_operator(next)
                adding = next == '+'
                while tokens:
                    next = tokens.pop(0)
                    if next in operators:
                        # The token is an operator: update the current
                        # activity:
                        adding = next == '+'
                    else:
                        # Then the token is a path whose visibility to change
                        check_node(next)
                        if adding:
                            forest.switch_on(next)
                        else:
                            forest.switch_off(next)
            # Store the result of this line as a slide :)
            slides.append(forest.summary)
        animate(slides, anim_suffix)
    else:
        # if not, do it in plain order and add no suffix
        # TODO: this is old script. not working anymore.
        for i, id in enumerate(layers):
            slides += [{'visible': layers[:(i + 1)],
                        'hidden' : layers[(i+1):]}]
        animate(slides)

    log("Cleanup..")
    for file in temp_files:
        out = popres('rm %s' % file)

    log("done.\n")

