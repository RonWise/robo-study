"""Run a real CUDA kernel through the host driver, without installing a toolkit."""
import ctypes as C

cuda = C.CDLL('libcuda.so.1')

def api(name, args):
    fn = getattr(cuda, name)
    fn.argtypes = args
    fn.restype = C.c_int
    return fn

get_error = api('cuGetErrorName', [C.c_int, C.POINTER(C.c_char_p)])

def check(result):
    if result:
        name = C.c_char_p()
        get_error(result, C.byref(name))
        raise RuntimeError(f'CUDA error {result}: {name.value}')

init = api('cuInit', [C.c_uint])
dev_get = api('cuDeviceGet', [C.POINTER(C.c_int), C.c_int])
dev_name = api('cuDeviceGetName', [C.c_char_p, C.c_int, C.c_int])
ctx_create = api('cuCtxCreate_v2', [C.POINTER(C.c_void_p), C.c_uint, C.c_int])
ctx_destroy = api('cuCtxDestroy_v2', [C.c_void_p])
module_load = api('cuModuleLoadData', [C.POINTER(C.c_void_p), C.c_void_p])
get_function = api('cuModuleGetFunction', [C.POINTER(C.c_void_p), C.c_void_p, C.c_char_p])
mem_alloc = api('cuMemAlloc_v2', [C.POINTER(C.c_uint64), C.c_size_t])
mem_free = api('cuMemFree_v2', [C.c_uint64])
launch = api('cuLaunchKernel', [C.c_void_p] + [C.c_uint] * 7 + [C.c_void_p, C.POINTER(C.c_void_p), C.POINTER(C.c_void_p)])
sync = api('cuCtxSynchronize', [])
copy_back = api('cuMemcpyDtoH_v2', [C.c_void_p, C.c_uint64, C.c_size_t])

ptx = b'''
.version 8.0
.target sm_80
.address_size 64
.visible .entry fill(.param .u64 output, .param .u32 count)
{
    .reg .pred %p;
    .reg .b32 %r<7>;
    .reg .b64 %rd<4>;
    ld.param.u64 %rd1, [output];
    ld.param.u32 %r1, [count];
    mov.u32 %r2, %ctaid.x;
    mov.u32 %r3, %ntid.x;
    mov.u32 %r4, %tid.x;
    mad.lo.u32 %r5, %r2, %r3, %r4;
    setp.ge.u32 %p, %r5, %r1;
    @%p bra DONE;
    mad.lo.u32 %r6, %r5, 3, 7;
    mul.wide.u32 %rd2, %r5, 4;
    add.u64 %rd3, %rd1, %rd2;
    st.global.u32 [%rd3], %r6;
DONE:
    ret;
}
'''
check(init(0))
dev = C.c_int()
check(dev_get(C.byref(dev), 0))
name = C.create_string_buffer(256)
check(dev_name(name, len(name), dev))
print('CUDA device:', name.value.decode(), flush=True)
ctx = C.c_void_p()
check(ctx_create(C.byref(ctx), 0, dev))
ptr = C.c_uint64()
try:
    module = C.c_void_p()
    check(module_load(C.byref(module), C.cast(C.c_char_p(ptx), C.c_void_p)))
    function = C.c_void_p()
    check(get_function(C.byref(function), module, b'fill'))
    count = C.c_uint(4096)
    result = (C.c_uint32 * count.value)()
    check(mem_alloc(C.byref(ptr), C.sizeof(result)))
    params = (C.c_void_p * 2)(C.cast(C.byref(ptr), C.c_void_p), C.cast(C.byref(count), C.c_void_p))
    check(launch(function, (count.value + 255) // 256, 1, 1, 256, 1, 1, 0, None, params, None))
    check(sync())
    check(copy_back(result, ptr, C.sizeof(result)))
    assert list(result) == [i * 3 + 7 for i in range(count.value)], 'GPU result mismatch'
    print('PASS: GPU computed all 4096 values correctly (3*i+7).')
finally:
    if ptr.value:
        mem_free(ptr)
    ctx_destroy(ctx)
