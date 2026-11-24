"""Linux defense-in-depth for reviewed workloads, NOT an arbitrary-code tenant sandbox.

Landlock ABI 4+ restricts filesystem and TCP access; libseccomp removes other
outbound connection and process-inspection paths. Fail closed on unsupported hosts.
"""
import ctypes as C
import errno
import os
import platform
import resource
import socket
from pathlib import Path

LIBC = C.CDLL(None, use_errno=True)
SYS_CREATE, SYS_ADD, SYS_RESTRICT = 444, 445, 446
READ_FILE, READ_DIR, EXECUTE = 1 << 2, 1 << 3, 1
FS = (1 << 15) - 1  # ABI 3 filesystem rights, including REFER and TRUNCATE
NET = 3  # BIND_TCP | CONNECT_TCP
READ = READ_FILE | READ_DIR
WRITE = FS & ~(EXECUTE | READ)
FILE_RIGHTS = EXECUTE | READ_FILE | (1 << 1) | (1 << 14)

class Ruleset(C.Structure):
    _fields_ = [("fs", C.c_uint64), ("net", C.c_uint64)]

class PathRule(C.Structure):
    _pack_ = 1
    _fields_ = [("access", C.c_uint64), ("fd", C.c_int32)]

class NetRule(C.Structure):
    _fields_ = [("access", C.c_uint64), ("port", C.c_uint64)]

class Arg(C.Structure):
    _fields_ = [("arg", C.c_uint), ("op", C.c_int), ("a", C.c_uint64), ("b", C.c_uint64)]

def checked(result, label):
    if result < 0:
        n=C.get_errno()
        raise OSError(n, label + ": " + os.strerror(n))
    return result

def abi():
    if platform.system() != "Linux" or platform.machine() not in ("x86_64","aarch64"):
        return 0
    return max(0, LIBC.syscall(SYS_CREATE,0,0,1))

def available():
    try:
        return abi() >= 4 and bool(C.CDLL("libseccomp.so.2"))
    except OSError:
        return False

def filter_syscalls():
    lib=C.CDLL("libseccomp.so.2")
    lib.seccomp_init.argtypes=[C.c_uint32];lib.seccomp_init.restype=C.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes=[C.c_char_p];lib.seccomp_syscall_resolve_name.restype=C.c_int
    lib.seccomp_rule_add_array.argtypes=[C.c_void_p,C.c_uint32,C.c_int,C.c_uint,C.POINTER(Arg)]
    lib.seccomp_load.argtypes=[C.c_void_p];lib.seccomp_release.argtypes=[C.c_void_p]
    ctx=lib.seccomp_init(0x7fff0000)  # ALLOW; explicit defense-in-depth deny rules
    if not ctx:raise RuntimeError("seccomp initialization failed")
    deny=0x00050000 | errno.EPERM
    def rule(name,*args):
        nr=lib.seccomp_syscall_resolve_name(name.encode())
        if nr < 0:raise RuntimeError("Required syscall filter unavailable: "+name)
        arr=(Arg*len(args))(*args)
        if lib.seccomp_rule_add_array(ctx,deny,nr,len(args),arr)!=0:
            raise RuntimeError("Cannot configure syscall filter: "+name)
    try:
        for name in ("connect","ptrace","process_vm_readv","process_vm_writev","pidfd_getfd",
                     "pidfd_send_signal","pidfd_open","kill","tkill","tgkill","rt_sigqueueinfo","rt_tgsigqueueinfo","io_uring_setup","unshare","setns",
                     "mount","umount2","bpf","keyctl","perf_event_open"):
            rule(name)
        # Only IPv4 stream sockets may be created. UNIX socketpair is still
        # available for internal event-loop wakeups; no external connect calls.
        rule("socket",Arg(0,1,socket.AF_INET,0)) # NE
        for kind in range(16):
            if kind != socket.SOCK_STREAM:
                rule("socket",Arg(1,7,15,kind)) # MASKED_EQ
        if lib.seccomp_load(ctx)!=0:raise RuntimeError("Cannot load syscall filter")
    finally:lib.seccomp_release(ctx)

def restrict(profile):
    if not available():raise RuntimeError("Restricted workload policy requires Landlock ABI 4 and libseccomp")
    port=profile["port"]
    if type(port)!=int or not 1024<=port<=65535:raise ValueError("Invalid sandbox port")
    read=[Path(p) for p in profile["read"]]
    write=[Path(p) for p in profile.get("write",[])]
    executable=Path(profile["executable"]).resolve(strict=True)
    # Explicitly permit runtime libraries, not the WebOps repository or data root.
    for p in ("/usr/lib","/usr/local/lib","/lib","/lib64","/etc/ld.so.cache",
              "/etc/localtime","/etc/nsswitch.conf","/etc/hosts","/etc/resolv.conf",
              "/proc/self","/proc/cpuinfo","/proc/meminfo","/sys/devices/system/cpu",
              "/dev/urandom","/dev/random"):
        if Path(p).exists():read.append(Path(p))
    if Path("/dev/null").exists():write.append(Path("/dev/null"))
    # Load the library before filesystem restriction, then filter syscall paths.
    checked(LIBC.prctl(38,1,0,0,0),"no_new_privs")
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_NOFILE,(1024,1024))
    for entry in os.listdir("/proc/self/fd"):
        fd=int(entry)
        if fd>2:
            try:os.close(fd)
            except OSError:pass
    attr=Ruleset(FS,NET)
    fd=checked(LIBC.syscall(SYS_CREATE,C.byref(attr),C.sizeof(attr),0),"Landlock create")
    def path_rule(path,access):
        path=path.resolve(strict=True)
        if not path.is_dir():access &= FILE_RIGHTS
        pfd=os.open(path,os.O_PATH|os.O_CLOEXEC)
        try:
            rule=PathRule(access,pfd)
            checked(LIBC.syscall(SYS_ADD,fd,1,C.byref(rule),0),"Landlock path rule")
        finally:os.close(pfd)
    try:
        for p in read:path_rule(p,READ)
        for p in write:path_rule(p,READ|WRITE)
        path_rule(executable,READ_FILE|EXECUTE)
        # ELF interpreter also needs EXECUTE permission.
        for loader in ("/lib64/ld-linux-x86-64.so.2","/lib/ld-linux-aarch64.so.1"):
            if Path(loader).exists():path_rule(Path(loader),READ_FILE|EXECUTE)
        rule=NetRule(1,port)
        checked(LIBC.syscall(SYS_ADD,fd,2,C.byref(rule),0),"Landlock bind rule")
        filter_syscalls()
        checked(LIBC.syscall(SYS_RESTRICT,fd,0),"Landlock restrict")
    finally:os.close(fd)
