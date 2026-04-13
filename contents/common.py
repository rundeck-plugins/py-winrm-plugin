import re
import os


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


def _redact_proxy_url(url):
    """Redact userinfo from proxy URL for safe logging."""
    if not url:
        return url
    try:
        try:
            from urllib.parse import urlparse, urlunparse
        except ImportError:
            from urlparse import urlparse, urlunparse
        parsed = urlparse(url)
        if parsed.username or parsed.password:
            netloc = parsed.hostname or ''
            if parsed.port:
                netloc += ':%s' % parsed.port
            return urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        return '[REDACTED]'
    return url


def configure_proxy(arguments, winrmproxy, winrmnoproxy, endpoint, log):
    try:
        from requests.utils import should_bypass_proxies
    except (ImportError, AttributeError):
        log.warning("requests.utils.should_bypass_proxies not available; NO_PROXY requires requests >= 2.14.0")
        if winrmproxy:
            arguments["proxy"] = winrmproxy
            log.info("Connecting to %s via PROXY (%s)" % (endpoint, _redact_proxy_url(winrmproxy)))
        return arguments

    if winrmproxy:
        if winrmnoproxy:
            # Delegate to requests via env vars so NO_PROXY matching works
            os.environ['HTTP_PROXY'] = winrmproxy
            os.environ['HTTPS_PROXY'] = winrmproxy
            os.environ['NO_PROXY'] = winrmnoproxy
            log.debug("Proxy via env vars: HTTP(S)_PROXY set, NO_PROXY=%s" % winrmnoproxy)

            if should_bypass_proxies(endpoint, no_proxy=winrmnoproxy):
                log.info("Connecting to %s DIRECTLY (matched NO_PROXY: %s)" % (endpoint, winrmnoproxy))
            else:
                log.info("Connecting to %s via PROXY (%s)" % (endpoint, _redact_proxy_url(winrmproxy)))
        else:
            # Legacy: explicit proxy for all connections
            arguments["proxy"] = winrmproxy
            log.info("Connecting to %s via PROXY (%s)" % (endpoint, _redact_proxy_url(winrmproxy)))
    else:
        if winrmnoproxy:
            log.warning("noproxy is set but no proxy configured; noproxy ignored")
        log.info("Connecting to %s DIRECTLY (no proxy configured)" % endpoint)
    return arguments
