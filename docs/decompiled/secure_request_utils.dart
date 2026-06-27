// lib: , url: package:carlinko/http_tools/secure_request_utils.dart

// class id: 1048823, size: 0x8
class :: {
}

// class id: 6192, size: 0x8, field offset: 0x8
abstract class SecureRequestUtils extends Object {

  static _ generateHMAC(/* No info */) {
    // ** addr: 0x73e4c8, size: 0x90
    // 0x73e4c8: EnterFrame
    //     0x73e4c8: stp             fp, lr, [SP, #-0x10]!
    //     0x73e4cc: mov             fp, SP
    // 0x73e4d0: AllocStack(0x10)
    //     0x73e4d0: sub             SP, SP, #0x10
    // 0x73e4d4: SetupParameters(dynamic _ /* r1 => r0, fp-0x8 */)
    //     0x73e4d4: mov             x0, x1
    //     0x73e4d8: stur            x1, [fp, #-8]
    // 0x73e4dc: CheckStackOverflow
    //     0x73e4dc: ldr             x16, [THR, #0x48]  ; THR::stack_limit
    //     0x73e4e0: cmp             SP, x16
    //     0x73e4e4: b.ls            #0x73e550
    // 0x73e4e8: r1 = Instance_Utf8Encoder
    //     0x73e4e8: ldr             x1, [PP, #0x1160]  ; [pp+0x1160] Obj!Utf8Encoder@e89671
    // 0x73e4ec: r2 = "<SIGN_KEY>"
    //     0x73e4ec: add             x2, PP, #0x13, lsl #12  ; [pp+0x13e20] "<SIGN_KEY>"
    //     0x73e4f0: ldr             x2, [x2, #0xe20]
    // 0x73e4f4: r4 = const [0, 0x2, 0, 0x2, null]
    //     0x73e4f4: ldr             x4, [PP, #0xc8]  ; [pp+0xc8] List(5) [0, 0x2, 0, 0x2, Null]
    // 0x73e4f8: r0 = convert()
    //     0x73e4f8: bl              #0xf32580  ; [dart:convert] Utf8Encoder::convert
    // 0x73e4fc: r1 = <List<int>, Digest>
    //     0x73e4fc: add             x1, PP, #0x13, lsl #12  ; [pp+0x13e28] TypeArguments: <List<int>, Digest>
    //     0x73e500: ldr             x1, [x1, #0xe28]
    // 0x73e504: stur            x0, [fp, #-0x10]
    // 0x73e508: r0 = Hmac()
    //     0x73e508: bl              #0x73e814  ; AllocateHmacStub -> Hmac (size=0x14)
    // 0x73e50c: mov             x1, x0
    // 0x73e510: ldur            x2, [fp, #-0x10]
    // 0x73e514: stur            x0, [fp, #-0x10]
    // 0x73e518: r0 = Hmac()
    //     0x73e518: bl              #0x73e558  ; [package:crypto/src/hmac.dart] Hmac::Hmac
    // 0x73e51c: ldur            x2, [fp, #-8]
    // 0x73e520: r1 = Instance_Utf8Encoder
    //     0x73e520: ldr             x1, [PP, #0x1160]  ; [pp+0x1160] Obj!Utf8Encoder@e89671
    // 0x73e524: r4 = const [0, 0x2, 0, 0x2, null]
    //     0x73e524: ldr             x4, [PP, #0xc8]  ; [pp+0xc8] List(5) [0, 0x2, 0, 0x2, Null]
    // 0x73e528: r0 = convert()
    //     0x73e528: bl              #0xf32580  ; [dart:convert] Utf8Encoder::convert
    // 0x73e52c: ldur            x1, [fp, #-0x10]
    // 0x73e530: mov             x2, x0
    // 0x73e534: r0 = convert()
    //     0x73e534: bl              #0xf33900  ; [package:crypto/src/hmac.dart] Hmac::convert
    // 0x73e538: LoadField: r1 = r0->field_7
    //     0x73e538: ldur            w1, [x0, #7]
    // 0x73e53c: DecompressPointer r1
    //     0x73e53c: add             x1, x1, HEAP, lsl #32
    // 0x73e540: r0 = base64Encode()
    //     0x73e540: bl              #0x6f4aac  ; [dart:convert] ::base64Encode
    // 0x73e544: LeaveFrame
    //     0x73e544: mov             SP, fp
    //     0x73e548: ldp             fp, lr, [SP], #0x10
    // 0x73e54c: ret
    //     0x73e54c: ret             
    // 0x73e550: r0 = StackOverflowSharedWithoutFPURegs()
    //     0x73e550: bl              #0x10b9d24  ; StackOverflowSharedWithoutFPURegsStub
    // 0x73e554: b               #0x73e4e8
  }
  static _ sortParams(/* No info */) {
    // ** addr: 0x73e820, size: 0xc8
    // 0x73e820: EnterFrame
    //     0x73e820: stp             fp, lr, [SP, #-0x10]!
    //     0x73e824: mov             fp, SP
    // 0x73e828: AllocStack(0x10)
    //     0x73e828: sub             SP, SP, #0x10
    // 0x73e82c: CheckStackOverflow
    //     0x73e82c: ldr             x16, [THR, #0x48]  ; THR::stack_limit
    //     0x73e830: cmp             SP, x16
    //     0x73e834: b.ls            #0x73e8e0
    // 0x73e838: r0 = jsonDecode()
    //     0x73e838: bl              #0x73e938  ; [dart:convert] ::jsonDecode
    // 0x73e83c: mov             x3, x0
    // 0x73e840: r2 = Null
    //     0x73e840: mov             x2, NULL
    // 0x73e844: r1 = Null
    //     0x73e844: mov             x1, NULL
    // 0x73e848: stur            x3, [fp, #-8]
    // 0x73e84c: r8 = Map<String, dynamic>
    //     0x73e84c: ldr             x8, [PP, #0x2e40]  ; [pp+0x2e40] Type: Map<String, dynamic>
    // 0x73e850: r3 = Null
    //     0x73e850: add             x3, PP, #0x13, lsl #12  ; [pp+0x13e70] Null
    //     0x73e854: ldr             x3, [x3, #0xe70]
    // 0x73e858: r0 = Map<String, dynamic>()
    //     0x73e858: bl              #0x676db8  ; IsType_Map<String, dynamic>_Stub
    // 0x73e85c: ldur            x0, [fp, #-8]
    // 0x73e860: LoadField: r2 = r0->field_7
    //     0x73e860: ldur            w2, [x0, #7]
    // 0x73e864: DecompressPointer r2
    //     0x73e864: add             x2, x2, HEAP, lsl #32
    // 0x73e868: r1 = Null
    //     0x73e868: mov             x1, NULL
    // 0x73e86c: r3 = <MapEntry<X0, X1>, X0, X1>
    //     0x73e86c: ldr             x3, [PP, #0xe58]  ; [pp+0xe58] TypeArguments: <MapEntry<X0, X1>, X0, X1>
    // 0x73e870: r30 = InstantiateTypeArgumentsStub
    //     0x73e870: ldr             lr, [PP, #0x1c0]  ; [pp+0x1c0] Stub: InstantiateTypeArguments (0x640f4c)
    // 0x73e874: LoadField: r30 = r30->field_7
    //     0x73e874: ldur            lr, [lr, #7]
    // 0x73e878: blr             lr
    // 0x73e87c: mov             x1, x0
    // 0x73e880: r0 = _CompactEntriesIterable()
    //     0x73e880: bl              #0x6738ac  ; Allocate_CompactEntriesIterableStub -> _CompactEntriesIterable<C1X0, C1X1> (size=0x10)
    // 0x73e884: mov             x1, x0
    // 0x73e888: ldur            x0, [fp, #-8]
    // 0x73e88c: StoreField: r1->field_b = r0
    //     0x73e88c: stur            w0, [x1, #0xb]
    // 0x73e890: r4 = const [0, 0x1, 0, 0x1, null]
    //     0x73e890: ldr             x4, [PP, #0xf0]  ; [pp+0xf0] List(5) [0, 0x1, 0, 0x1, Null]
    // 0x73e894: r0 = toList()
    //     0x73e894: bl              #0xa36380  ; [dart:core] Iterable::toList
    // 0x73e898: r1 = Function '<anonymous closure>': static.
    //     0x73e898: add             x1, PP, #0x13, lsl #12  ; [pp+0x13e80] AnonymousClosure: static (0x73e97c), in [package:carlinko/http_tools/secure_request_utils.dart] SecureRequestUtils::sortParams (0x73e820)
    //     0x73e89c: ldr             x1, [x1, #0xe80]
    // 0x73e8a0: r2 = Null
    //     0x73e8a0: mov             x2, NULL
    // 0x73e8a4: stur            x0, [fp, #-8]
    // 0x73e8a8: r0 = AllocateClosure()
    //     0x73e8a8: bl              #0x10b8f50  ; AllocateClosureStub
    // 0x73e8ac: str             x0, [SP]
    // 0x73e8b0: ldur            x1, [fp, #-8]
    // 0x73e8b4: r4 = const [0, 0x2, 0x1, 0x2, null]
    //     0x73e8b4: ldr             x4, [PP, #0xc90]  ; [pp+0xc90] List(5) [0, 0x2, 0x1, 0x2, Null]
    // 0x73e8b8: r0 = sort()
    //     0x73e8b8: bl              #0x6afa5c  ; [dart:collection] ListBase::sort
    // 0x73e8bc: ldur            x2, [fp, #-8]
    // 0x73e8c0: r1 = <String, dynamic>
    //     0x73e8c0: ldr             x1, [PP, #0x20d0]  ; [pp+0x20d0] TypeArguments: <String, dynamic>
    // 0x73e8c4: r0 = Map.fromEntries()
    //     0x73e8c4: bl              #0x73e8e8  ; [dart:core] Map::Map.fromEntries
    // 0x73e8c8: mov             x1, x0
    // 0x73e8cc: r4 = const [0, 0x1, 0, 0x1, null]
    //     0x73e8cc: ldr             x4, [PP, #0xf0]  ; [pp+0xf0] List(5) [0, 0x1, 0, 0x1, Null]
    // 0x73e8d0: r0 = jsonEncode()
    //     0x73e8d0: bl              #0x7036b0  ; [dart:convert] ::jsonEncode
    // 0x73e8d4: LeaveFrame
    //     0x73e8d4: mov             SP, fp
    //     0x73e8d8: ldp             fp, lr, [SP], #0x10
    // 0x73e8dc: ret
    //     0x73e8dc: ret             
    // 0x73e8e0: r0 = StackOverflowSharedWithoutFPURegs()
    //     0x73e8e0: bl              #0x10b9d24  ; StackOverflowSharedWithoutFPURegsStub
    // 0x73e8e4: b               #0x73e838
  }
  [closure] static int <anonymous closure>(dynamic, MapEntry<String, dynamic>, MapEntry<String, dynamic>) {
    // ** addr: 0x73e97c, size: 0x68
    // 0x73e97c: EnterFrame
    //     0x73e97c: stp             fp, lr, [SP, #-0x10]!
    //     0x73e980: mov             fp, SP
    // 0x73e984: CheckStackOverflow
    //     0x73e984: ldr             x16, [THR, #0x48]  ; THR::stack_limit
    //     0x73e988: cmp             SP, x16
    //     0x73e98c: b.ls            #0x73e9d8
    // 0x73e990: ldr             x0, [fp, #0x18]
    // 0x73e994: LoadField: r1 = r0->field_b
    //     0x73e994: ldur            w1, [x0, #0xb]
    // 0x73e998: DecompressPointer r1
    //     0x73e998: add             x1, x1, HEAP, lsl #32
    // 0x73e99c: ldr             x0, [fp, #0x10]
    // 0x73e9a0: LoadField: r2 = r0->field_b
    //     0x73e9a0: ldur            w2, [x0, #0xb]
    // 0x73e9a4: DecompressPointer r2
    //     0x73e9a4: add             x2, x2, HEAP, lsl #32
    // 0x73e9a8: cmp             w1, NULL
    // 0x73e9ac: b.eq            #0x73e9e0
    // 0x73e9b0: r0 = compareTo()
    //     0x73e9b0: bl              #0xe4eb48  ; [dart:core] _StringBase::compareTo
    // 0x73e9b4: mov             x2, x0
    // 0x73e9b8: r0 = BoxInt64Instr(r2)
    //     0x73e9b8: sbfiz           x0, x2, #1, #0x1f
    //     0x73e9bc: cmp             x2, x0, asr #1
    //     0x73e9c0: b.eq            #0x73e9cc
    //     0x73e9c4: bl              #0x10b9ea4  ; AllocateMintSharedWithoutFPURegsStub
    //     0x73e9c8: stur            x2, [x0, #7]
    // 0x73e9cc: LeaveFrame
    //     0x73e9cc: mov             SP, fp
    //     0x73e9d0: ldp             fp, lr, [SP], #0x10
    // 0x73e9d4: ret
    //     0x73e9d4: ret             
    // 0x73e9d8: r0 = StackOverflowSharedWithoutFPURegs()
    //     0x73e9d8: bl              #0x10b9d24  ; StackOverflowSharedWithoutFPURegsStub
    // 0x73e9dc: b               #0x73e990
    // 0x73e9e0: r0 = NullErrorSharedWithoutFPURegs()
    //     0x73e9e0: bl              #0x10ba55c  ; NullErrorSharedWithoutFPURegsStub
  }
}
