
def tryFloat(str):
    negative = 1.0
    if type(str) is float: 
        return str
    str = str.replace(',', '')
    str = str.replace('$', '')
    str = str.replace('S', '')
    if '(' in str: negative = -1.0
    str = str.replace('(', '')
    str = str.replace(')', '')
    try:
        retFloat = negative * float(str)
    except:
        retFloat = None
    return retFloat


def strfloat(floatval, int_places=2):
    formatstr = '{:.'+ str(int_places) +'f}'
    return formatstr.format(floatval)