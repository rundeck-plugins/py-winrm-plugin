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


def replace_single_quotes_format(command):
    command = command + " "
    command = re.sub(r'\s(\')',' \"', command)
    command = re.sub(r'(\')\s','\" ', command)
    command = re.sub(r'\'("\'")\'', "\'", command)

    return command
