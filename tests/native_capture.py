"""Capture this process's Tk window using AppKit, without desktop capture permission."""
import ctypes as C
from pathlib import Path


class Point(C.Structure):
    _fields_ = [('x', C.c_double), ('y', C.c_double)]


class Size(C.Structure):
    _fields_ = [('width', C.c_double), ('height', C.c_double)]


class Rect(C.Structure):
    _fields_ = [('origin', Point), ('size', Size)]


def capture(path):
    objc = C.CDLL('/usr/lib/libobjc.A.dylib')
    C.CDLL('/System/Library/Frameworks/AppKit.framework/AppKit')
    objc.objc_getClass.argtypes = [C.c_char_p]
    objc.objc_getClass.restype = C.c_void_p
    objc.sel_registerName.argtypes = [C.c_char_p]
    objc.sel_registerName.restype = C.c_void_p
    def send(receiver, name, restype=C.c_void_p, types=(), args=()):
        call = C.CFUNCTYPE(restype, C.c_void_p, C.c_void_p, *types)(('objc_msgSend', objc))
        return call(receiver, objc.sel_registerName(name.encode()), *args)
    app = send(objc.objc_getClass(b'NSApplication'), 'sharedApplication')
    windows = send(app, 'windows')
    count = send(windows, 'count', C.c_ulong)
    window = None
    for index in range(count):
        item = send(windows, 'objectAtIndex:', types=(C.c_ulong,), args=(index,))
        if send(item, 'isVisible', C.c_bool):
            window = item
            break
    if not window:
        raise RuntimeError('No visible window in this process')
    view = send(window, 'contentView')
    bounds = send(view, 'bounds', Rect)
    rep = send(view, 'bitmapImageRepForCachingDisplayInRect:', types=(Rect,), args=(bounds,))
    if not rep:
        raise RuntimeError('AppKit cannot allocate view capture')
    send(view, 'cacheDisplayInRect:toBitmapImageRep:', None, (Rect, C.c_void_p), (bounds, rep))
    properties = send(objc.objc_getClass(b'NSDictionary'), 'dictionary')
    data = send(rep, 'representationUsingType:properties:', types=(C.c_ulong, C.c_void_p), args=(4, properties))
    target = str(Path(path).resolve()).encode()
    filename = send(objc.objc_getClass(b'NSString'), 'stringWithUTF8String:', types=(C.c_char_p,), args=(target,))
    if not send(data, 'writeToFile:atomically:', C.c_bool, (C.c_void_p, C.c_bool), (filename, True)):
        raise RuntimeError('Could not save native window capture')
    return str(Path(path).resolve())
