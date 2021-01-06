import re


def check_is_file(destination):
    # check if destination file is a file
    regex = r"((?:(?:[cC]:))[^\.]+\.[A-Za-z]{3})"

    matches = re.finditer(regex, destination, re.MULTILINE)
    isfile = False

    for matchNum, match in enumerate(matches):
        isfile = True

    return isfile


def get_file(destination):
    filename = ""
    split = "/"
    if("\\" in destination):
        split = "\\"

    for file in destination.split(split):
        filename = file

    return filename

def removeSimpleQuotes(command):
   result = cleanSimpleQuoteCommand(command)

   return result

def isAPathThatRequiresDoubleQuotes(candidate):
    #first check that this is not multiple paths, e.g. 'C:\windows C:\tmp...'
    regexpMultipleAbsolutePath = re.compile('\'[a-zA-Z]:\\\\.*\s[a-zA-Z]:\\\\.*') #at least two absolute paths
    if regexpMultipleAbsolutePath.match(candidate): return False

    #verify if this is a path with no options after, windows style. e.g. 'C:\Windows /w...'
    regexpPathAndOption = re.compile('\'[a-zA-Z]:\\\\.*\s/.+')
    if regexpPathAndOption.match(candidate): return False

    #verify if this is a path with no options after, unix style. e.g. 'C:\Windows -v'
    regexpPathAndOptionUnix = re.compile('\'[a-zA-Z]:\\\\.*\s-.+')
    if regexpPathAndOptionUnix.match(candidate): return False

    #finally, check if this is a single path, with single quotes, and requires to be put between double quotes.e.g. 'C:\Program Files'
    regexPathRequireQuotes = re.compile('\'[a-zA-Z]:\\\\.*\s')
    if regexPathRequireQuotes.match(candidate):
        return True
    else:
        return False

def cleanSimpleQuoteCommand(command):
    result = re.sub(r'(\'.+?\')\s', conditionalReplace, ' '+command+' ' )
    return result

def conditionalReplace( aMatch ) :
    result = ''
    capturedGroup = aMatch.group(1)
    capturedGroup = capturedGroup.strip()

    result = capturedGroup[1:(len(capturedGroup)-1)]
    if isAPathThatRequiresDoubleQuotes(capturedGroup):
        result = '"' + result + '"'

    return result+' '
