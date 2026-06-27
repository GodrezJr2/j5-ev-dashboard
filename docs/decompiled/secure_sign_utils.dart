// lib: , url: package:carlinko/http_tools/secure_sign_utils.dart

// class id: 1048824, size: 0x8
class :: {
}

// class id: 6191, size: 0x8, field offset: 0x8
abstract class SecureSignUtils extends Object {

  static _ signMethod(/* No info */) {
    // ** addr: 0x73e40c, size: 0xbc
    // 0x73e40c: EnterFrame
    //     0x73e40c: stp             fp, lr, [SP, #-0x10]!
    //     0x73e410: mov             fp, SP
    // 0x73e414: AllocStack(0x28)
    //     0x73e414: sub             SP, SP, #0x28
    // 0x73e418: SetupParameters(dynamic _ /* r1 => r1, fp-0x8 */)
    //     0x73e418: stur            x1, [fp, #-8]
    // 0x73e41c: CheckStackOverflow
    //     0x73e41c: ldr             x16, [THR, #0x48]  ; THR::stack_limit
    //     0x73e420: cmp             SP, x16
    //     0x73e424: b.ls            #0x73e4c0
    // 0x73e428: cmp             x2, #1
    // 0x73e42c: b.ne            #0x73e498
    // 0x73e430: r16 = <String, String>
    //     0x73e430: add             x16, PP, #9, lsl #12  ; [pp+0x9b70] TypeArguments: <String, String>
    //     0x73e434: ldr             x16, [x16, #0xb70]
    // 0x73e438: ldr             lr, [THR, #0xa0]  ; THR::empty_array
    // 0x73e43c: stp             lr, x16, [SP]
    // 0x73e440: r0 = Map._fromLiteral()
    //     0x73e440: bl              #0x674c48  ; [dart:core] Map::Map._fromLiteral
    // 0x73e444: stur            x0, [fp, #-0x10]
    // 0x73e448: r1 = 1
    //     0x73e448: movz            x1, #0x1
    // 0x73e44c: r0 = AllocateContext()
    //     0x73e44c: bl              #0x10b8b8c  ; AllocateContextStub
    // 0x73e450: mov             x3, x0
    // 0x73e454: ldur            x0, [fp, #-0x10]
    // 0x73e458: stur            x3, [fp, #-0x18]
    // 0x73e45c: StoreField: r3->field_f = r0
    //     0x73e45c: stur            w0, [x3, #0xf]
    // 0x73e460: mov             x2, x3
    // 0x73e464: r1 = Function '<anonymous closure>': static.
    //     0x73e464: add             x1, PP, #0x13, lsl #12  ; [pp+0x13e18] AnonymousClosure: static (0x73e9e4), in [package:carlinko/http_tools/secure_sign_utils.dart] SecureSignUtils::signMethod (0x73e40c)
    //     0x73e468: ldr             x1, [x1, #0xe18]
    // 0x73e46c: r0 = AllocateClosure()
    //     0x73e46c: bl              #0x10b8f50  ; AllocateClosureStub
    // 0x73e470: ldur            x1, [fp, #-8]
    // 0x73e474: mov             x2, x0
    // 0x73e478: r0 = forEach()
    //     0x73e478: bl              #0xfc035c  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::forEach
    // 0x73e47c: ldur            x0, [fp, #-0x18]
    // 0x73e480: LoadField: r1 = r0->field_f
    //     0x73e480: ldur            w1, [x0, #0xf]
    // 0x73e484: DecompressPointer r1
    //     0x73e484: add             x1, x1, HEAP, lsl #32
    // 0x73e488: r4 = const [0, 0x1, 0, 0x1, null]
    //     0x73e488: ldr             x4, [PP, #0xf0]  ; [pp+0xf0] List(5) [0, 0x1, 0, 0x1, Null]
    // 0x73e48c: r0 = jsonEncode()
    //     0x73e48c: bl              #0x7036b0  ; [dart:convert] ::jsonEncode
    // 0x73e490: mov             x1, x0
    // 0x73e494: b               #0x73e4a8
    // 0x73e498: ldur            x1, [fp, #-8]
    // 0x73e49c: r4 = const [0, 0x1, 0, 0x1, null]
    //     0x73e49c: ldr             x4, [PP, #0xf0]  ; [pp+0xf0] List(5) [0, 0x1, 0, 0x1, Null]
    // 0x73e4a0: r0 = jsonEncode()
    //     0x73e4a0: bl              #0x7036b0  ; [dart:convert] ::jsonEncode
    // 0x73e4a4: mov             x1, x0
    // 0x73e4a8: r0 = sortParams()
    //     0x73e4a8: bl              #0x73e820  ; [package:carlinko/http_tools/secure_request_utils.dart] SecureRequestUtils::sortParams
    // 0x73e4ac: mov             x1, x0
    // 0x73e4b0: r0 = generateHMAC()
    //     0x73e4b0: bl              #0x73e4c8  ; [package:carlinko/http_tools/secure_request_utils.dart] SecureRequestUtils::generateHMAC
    // 0x73e4b4: LeaveFrame
    //     0x73e4b4: mov             SP, fp
    //     0x73e4b8: ldp             fp, lr, [SP], #0x10
    // 0x73e4bc: ret
    //     0x73e4bc: ret             
    // 0x73e4c0: r0 = StackOverflowSharedWithoutFPURegs()
    //     0x73e4c0: bl              #0x10b9d24  ; StackOverflowSharedWithoutFPURegsStub
    // 0x73e4c4: b               #0x73e428
  }
  [closure] static void <anonymous closure>(dynamic, String, dynamic) {
    // ** addr: 0x73e9e4, size: 0x88
    // 0x73e9e4: EnterFrame
    //     0x73e9e4: stp             fp, lr, [SP, #-0x10]!
    //     0x73e9e8: mov             fp, SP
    // 0x73e9ec: AllocStack(0x10)
    //     0x73e9ec: sub             SP, SP, #0x10
    // 0x73e9f0: SetupParameters([dynamic _ /* r0 */])
    //     0x73e9f0: ldr             x0, [fp, #0x20]
    //     0x73e9f4: ldur            w1, [x0, #0x17]
    //     0x73e9f8: add             x1, x1, HEAP, lsl #32
    // 0x73e9fc: CheckStackOverflow
    //     0x73e9fc: ldr             x16, [THR, #0x48]  ; THR::stack_limit
    //     0x73ea00: cmp             SP, x16
    //     0x73ea04: b.ls            #0x73ea64
    // 0x73ea08: LoadField: r2 = r1->field_f
    //     0x73ea08: ldur            w2, [x1, #0xf]
    // 0x73ea0c: DecompressPointer r2
    //     0x73ea0c: add             x2, x2, HEAP, lsl #32
    // 0x73ea10: ldr             x0, [fp, #0x10]
    // 0x73ea14: stur            x2, [fp, #-8]
    // 0x73ea18: r1 = 60
    //     0x73ea18: movz            x1, #0x3c
    // 0x73ea1c: branchIfSmi(r0, 0x73ea28)
    //     0x73ea1c: tbz             w0, #0, #0x73ea28
    // 0x73ea20: r1 = LoadClassIdInstr(r0)
    //     0x73ea20: ldur            x1, [x0, #-1]
    //     0x73ea24: ubfx            x1, x1, #0xc, #0x14
    // 0x73ea28: str             x0, [SP]
    // 0x73ea2c: mov             x0, x1
    // 0x73ea30: r4 = const [0, 0x1, 0x1, 0x1, null]
    //     0x73ea30: ldr             x4, [PP, #0x290]  ; [pp+0x290] List(5) [0, 0x1, 0x1, 0x1, Null]
    // 0x73ea34: r0 = GDT[cid_x0 + 0xa9e4]()
    //     0x73ea34: movz            x17, #0xa9e4
    //     0x73ea38: add             lr, x0, x17
    //     0x73ea3c: ldr             lr, [x21, lr, lsl #3]
    //     0x73ea40: blr             lr
    // 0x73ea44: ldur            x1, [fp, #-8]
    // 0x73ea48: ldr             x2, [fp, #0x18]
    // 0x73ea4c: mov             x3, x0
    // 0x73ea50: r0 = []=()
    //     0x73ea50: bl              #0xfd9ef8  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::[]=
    // 0x73ea54: r0 = Null
    //     0x73ea54: mov             x0, NULL
    // 0x73ea58: LeaveFrame
    //     0x73ea58: mov             SP, fp
    //     0x73ea5c: ldp             fp, lr, [SP], #0x10
    // 0x73ea60: ret
    //     0x73ea60: ret             
    // 0x73ea64: r0 = StackOverflowSharedWithoutFPURegs()
    //     0x73ea64: bl              #0x10b9d24  ; StackOverflowSharedWithoutFPURegsStub
    // 0x73ea68: b               #0x73ea08
  }
}
