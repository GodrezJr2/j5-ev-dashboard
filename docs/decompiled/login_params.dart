// lib: , url: package:carlinko/http_tools/request/login_params.dart

// class id: 1048757, size: 0x8
class :: {
}

// class id: 6305, size: 0x44, field offset: 0x8
class LoginParams extends Object {

  Map<String, dynamic> toJson(LoginParams) {
    // ** addr: 0xd3a5e0, size: 0x1d4
    // 0xd3a5e0: EnterFrame
    //     0xd3a5e0: stp             fp, lr, [SP, #-0x10]!
    //     0xd3a5e4: mov             fp, SP
    // 0xd3a5e8: AllocStack(0x20)
    //     0xd3a5e8: sub             SP, SP, #0x20
    // 0xd3a5ec: SetupParameters(LoginParams this /* r1 => r1, fp-0x8 */)
    //     0xd3a5ec: stur            x1, [fp, #-8]
    // 0xd3a5f0: CheckStackOverflow
    //     0xd3a5f0: ldr             x16, [THR, #0x48]  ; THR::stack_limit
    //     0xd3a5f4: cmp             SP, x16
    //     0xd3a5f8: b.ls            #0xd3a7ac
    // 0xd3a5fc: r16 = <String, dynamic>
    //     0xd3a5fc: ldr             x16, [PP, #0x20d0]  ; [pp+0x20d0] TypeArguments: <String, dynamic>
    // 0xd3a600: ldr             lr, [THR, #0xa0]  ; THR::empty_array
    // 0xd3a604: stp             lr, x16, [SP]
    // 0xd3a608: r0 = Map._fromLiteral()
    //     0xd3a608: bl              #0x674c48  ; [dart:core] Map::Map._fromLiteral
    // 0xd3a60c: mov             x4, x0
    // 0xd3a610: ldur            x0, [fp, #-8]
    // 0xd3a614: stur            x4, [fp, #-0x10]
    // 0xd3a618: LoadField: r3 = r0->field_7
    //     0xd3a618: ldur            w3, [x0, #7]
    // 0xd3a61c: DecompressPointer r3
    //     0xd3a61c: add             x3, x3, HEAP, lsl #32
    // 0xd3a620: mov             x1, x4
    // 0xd3a624: r2 = "account"
    //     0xd3a624: add             x2, PP, #0x22, lsl #12  ; [pp+0x22ac0] "account"
    //     0xd3a628: ldr             x2, [x2, #0xac0]
    // 0xd3a62c: r0 = []=()
    //     0xd3a62c: bl              #0xfd9ef8  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::[]=
    // 0xd3a630: ldur            x1, [fp, #-0x10]
    // 0xd3a634: r2 = "appType"
    //     0xd3a634: add             x2, PP, #0x22, lsl #12  ; [pp+0x22ac8] "appType"
    //     0xd3a638: ldr             x2, [x2, #0xac8]
    // 0xd3a63c: r3 = "APP"
    //     0xd3a63c: add             x3, PP, #0x22, lsl #12  ; [pp+0x22a88] "APP"
    //     0xd3a640: ldr             x3, [x3, #0xa88]
    // 0xd3a644: r0 = []=()
    //     0xd3a644: bl              #0xfd9ef8  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::[]=
    // 0xd3a648: ldur            x0, [fp, #-8]
    // 0xd3a64c: LoadField: r3 = r0->field_f
    //     0xd3a64c: ldur            w3, [x0, #0xf]
    // 0xd3a650: DecompressPointer r3
    //     0xd3a650: add             x3, x3, HEAP, lsl #32
    // 0xd3a654: ldur            x1, [fp, #-0x10]
    // 0xd3a658: r2 = "appVersion"
    //     0xd3a658: add             x2, PP, #0x22, lsl #12  ; [pp+0x22008] "appVersion"
    //     0xd3a65c: ldr             x2, [x2, #8]
    // 0xd3a660: r0 = []=()
    //     0xd3a660: bl              #0xfd9ef8  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::[]=
    // 0xd3a664: ldur            x0, [fp, #-8]
    // 0xd3a668: LoadField: r3 = r0->field_13
    //     0xd3a668: ldur            w3, [x0, #0x13]
    // 0xd3a66c: DecompressPointer r3
    //     0xd3a66c: add             x3, x3, HEAP, lsl #32
    // 0xd3a670: ldur            x1, [fp, #-0x10]
    // 0xd3a674: r2 = "dateTime"
    //     0xd3a674: add             x2, PP, #0x22, lsl #12  ; [pp+0x22ad0] "dateTime"
    //     0xd3a678: ldr             x2, [x2, #0xad0]
    // 0xd3a67c: r0 = []=()
    //     0xd3a67c: bl              #0xfd9ef8  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::[]=
    // 0xd3a680: ldur            x0, [fp, #-8]
    // 0xd3a684: ArrayLoad: r3 = r0[0]  ; List_4
    //     0xd3a684: ldur            w3, [x0, #0x17]
    // 0xd3a688: DecompressPointer r3
    //     0xd3a688: add             x3, x3, HEAP, lsl #32
    // 0xd3a68c: ldur            x1, [fp, #-0x10]
    // 0xd3a690: r2 = "language"
    //     0xd3a690: add             x2, PP, #0x21, lsl #12  ; [pp+0x21728] "language"
    //     0xd3a694: ldr             x2, [x2, #0x728]
    // 0xd3a698: r0 = []=()
    //     0xd3a698: bl              #0xfd9ef8  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::[]=
    // 0xd3a69c: ldur            x1, [fp, #-0x10]
    // 0xd3a6a0: r2 = "md5"
    //     0xd3a6a0: add             x2, PP, #0x22, lsl #12  ; [pp+0x22ad8] "md5"
    //     0xd3a6a4: ldr             x2, [x2, #0xad8]
    // 0xd3a6a8: r3 = ""
    //     0xd3a6a8: ldr             x3, [PP, #0x900]  ; [pp+0x900] ""
    // 0xd3a6ac: r0 = []=()
    //     0xd3a6ac: bl              #0xfd9ef8  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::[]=
    // 0xd3a6b0: ldur            x1, [fp, #-0x10]
    // 0xd3a6b4: r2 = "method"
    //     0xd3a6b4: add             x2, PP, #0xb, lsl #12  ; [pp+0xb3a8] "method"
    //     0xd3a6b8: ldr             x2, [x2, #0x3a8]
    // 0xd3a6bc: r3 = "PASSWORD"
    //     0xd3a6bc: add             x3, PP, #0x22, lsl #12  ; [pp+0x22a90] "PASSWORD"
    //     0xd3a6c0: ldr             x3, [x3, #0xa90]
    // 0xd3a6c4: r0 = []=()
    //     0xd3a6c4: bl              #0xfd9ef8  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::[]=
    // 0xd3a6c8: ldur            x1, [fp, #-0x10]
    // 0xd3a6cc: r2 = "osType"
    //     0xd3a6cc: add             x2, PP, #0x22, lsl #12  ; [pp+0x22ae0] "osType"
    //     0xd3a6d0: ldr             x2, [x2, #0xae0]
    // 0xd3a6d4: r3 = "ANDROID"
    //     0xd3a6d4: add             x3, PP, #0x22, lsl #12  ; [pp+0x22a98] "ANDROID"
    //     0xd3a6d8: ldr             x3, [x3, #0xa98]
    // 0xd3a6dc: r0 = []=()
    //     0xd3a6dc: bl              #0xfd9ef8  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::[]=
    // 0xd3a6e0: ldur            x0, [fp, #-8]
    // 0xd3a6e4: LoadField: r3 = r0->field_27
    //     0xd3a6e4: ldur            w3, [x0, #0x27]
    // 0xd3a6e8: DecompressPointer r3
    //     0xd3a6e8: add             x3, x3, HEAP, lsl #32
    // 0xd3a6ec: ldur            x1, [fp, #-0x10]
    // 0xd3a6f0: r2 = "osVersion"
    //     0xd3a6f0: add             x2, PP, #0x22, lsl #12  ; [pp+0x22ae8] "osVersion"
    //     0xd3a6f4: ldr             x2, [x2, #0xae8]
    // 0xd3a6f8: r0 = []=()
    //     0xd3a6f8: bl              #0xfd9ef8  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::[]=
    // 0xd3a6fc: ldur            x0, [fp, #-8]
    // 0xd3a700: LoadField: r3 = r0->field_2b
    //     0xd3a700: ldur            w3, [x0, #0x2b]
    // 0xd3a704: DecompressPointer r3
    //     0xd3a704: add             x3, x3, HEAP, lsl #32
    // 0xd3a708: ldur            x1, [fp, #-0x10]
    // 0xd3a70c: r2 = "password"
    //     0xd3a70c: add             x2, PP, #0x16, lsl #12  ; [pp+0x16350] "password"
    //     0xd3a710: ldr             x2, [x2, #0x350]
    // 0xd3a714: r0 = []=()
    //     0xd3a714: bl              #0xfd9ef8  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::[]=
    // 0xd3a718: ldur            x0, [fp, #-8]
    // 0xd3a71c: LoadField: r3 = r0->field_2f
    //     0xd3a71c: ldur            w3, [x0, #0x2f]
    // 0xd3a720: DecompressPointer r3
    //     0xd3a720: add             x3, x3, HEAP, lsl #32
    // 0xd3a724: ldur            x1, [fp, #-0x10]
    // 0xd3a728: r2 = "phoneBrand"
    //     0xd3a728: add             x2, PP, #0x22, lsl #12  ; [pp+0x22af0] "phoneBrand"
    //     0xd3a72c: ldr             x2, [x2, #0xaf0]
    // 0xd3a730: r0 = []=()
    //     0xd3a730: bl              #0xfd9ef8  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::[]=
    // 0xd3a734: ldur            x0, [fp, #-8]
    // 0xd3a738: LoadField: r3 = r0->field_33
    //     0xd3a738: ldur            w3, [x0, #0x33]
    // 0xd3a73c: DecompressPointer r3
    //     0xd3a73c: add             x3, x3, HEAP, lsl #32
    // 0xd3a740: ldur            x1, [fp, #-0x10]
    // 0xd3a744: r2 = "phoneModel"
    //     0xd3a744: add             x2, PP, #0x22, lsl #12  ; [pp+0x22af8] "phoneModel"
    //     0xd3a748: ldr             x2, [x2, #0xaf8]
    // 0xd3a74c: r0 = []=()
    //     0xd3a74c: bl              #0xfd9ef8  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::[]=
    // 0xd3a750: ldur            x0, [fp, #-8]
    // 0xd3a754: LoadField: r3 = r0->field_37
    //     0xd3a754: ldur            w3, [x0, #0x37]
    // 0xd3a758: DecompressPointer r3
    //     0xd3a758: add             x3, x3, HEAP, lsl #32
    // 0xd3a75c: ldur            x1, [fp, #-0x10]
    // 0xd3a760: r2 = "timeZone"
    //     0xd3a760: add             x2, PP, #0x22, lsl #12  ; [pp+0x22b00] "timeZone"
    //     0xd3a764: ldr             x2, [x2, #0xb00]
    // 0xd3a768: r0 = []=()
    //     0xd3a768: bl              #0xfd9ef8  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::[]=
    // 0xd3a76c: ldur            x1, [fp, #-0x10]
    // 0xd3a770: r2 = "verifyCode"
    //     0xd3a770: add             x2, PP, #0x22, lsl #12  ; [pp+0x22b08] "verifyCode"
    //     0xd3a774: ldr             x2, [x2, #0xb08]
    // 0xd3a778: r3 = ""
    //     0xd3a778: ldr             x3, [PP, #0x900]  ; [pp+0x900] ""
    // 0xd3a77c: r0 = []=()
    //     0xd3a77c: bl              #0xfd9ef8  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::[]=
    // 0xd3a780: ldur            x0, [fp, #-8]
    // 0xd3a784: LoadField: r3 = r0->field_3f
    //     0xd3a784: ldur            w3, [x0, #0x3f]
    // 0xd3a788: DecompressPointer r3
    //     0xd3a788: add             x3, x3, HEAP, lsl #32
    // 0xd3a78c: ldur            x1, [fp, #-0x10]
    // 0xd3a790: r2 = "appName"
    //     0xd3a790: add             x2, PP, #0x13, lsl #12  ; [pp+0x13f20] "appName"
    //     0xd3a794: ldr             x2, [x2, #0xf20]
    // 0xd3a798: r0 = []=()
    //     0xd3a798: bl              #0xfd9ef8  ; [dart:_compact_hash] __Map&_HashVMBase&MapMixin&_HashBase&_OperatorEqualsAndHashCode&_LinkedHashMapMixin::[]=
    // 0xd3a79c: ldur            x0, [fp, #-0x10]
    // 0xd3a7a0: LeaveFrame
    //     0xd3a7a0: mov             SP, fp
    //     0xd3a7a4: ldp             fp, lr, [SP], #0x10
    // 0xd3a7a8: ret
    //     0xd3a7a8: ret             
    // 0xd3a7ac: r0 = StackOverflowSharedWithoutFPURegs()
    //     0xd3a7ac: bl              #0x10b9d24  ; StackOverflowSharedWithoutFPURegsStub
    // 0xd3a7b0: b               #0xd3a5fc
  }
  Map<String, dynamic> toJson(LoginParams) {
    // ** addr: 0xd3a7cc, size: 0x48
    // 0xd3a7cc: EnterFrame
    //     0xd3a7cc: stp             fp, lr, [SP, #-0x10]!
    //     0xd3a7d0: mov             fp, SP
    // 0xd3a7d4: CheckStackOverflow
    //     0xd3a7d4: ldr             x16, [THR, #0x48]  ; THR::stack_limit
    //     0xd3a7d8: cmp             SP, x16
    //     0xd3a7dc: b.ls            #0xd3a7f4
    // 0xd3a7e0: ldr             x1, [fp, #0x10]
    // 0xd3a7e4: r0 = toJson()
    //     0xd3a7e4: bl              #0xd3a5e0  ; [package:carlinko/http_tools/request/login_params.dart] LoginParams::toJson
    // 0xd3a7e8: LeaveFrame
    //     0xd3a7e8: mov             SP, fp
    //     0xd3a7ec: ldp             fp, lr, [SP], #0x10
    // 0xd3a7f0: ret
    //     0xd3a7f0: ret             
    // 0xd3a7f4: r0 = StackOverflowSharedWithoutFPURegs()
    //     0xd3a7f4: bl              #0x10b9d24  ; StackOverflowSharedWithoutFPURegsStub
    // 0xd3a7f8: b               #0xd3a7e0
  }
  _ toString(/* No info */) {
    // ** addr: 0xe6bd28, size: 0x1b8
    // 0xe6bd28: EnterFrame
    //     0xe6bd28: stp             fp, lr, [SP, #-0x10]!
    //     0xe6bd2c: mov             fp, SP
    // 0xe6bd30: AllocStack(0x8)
    //     0xe6bd30: sub             SP, SP, #8
    // 0xe6bd34: CheckStackOverflow
    //     0xe6bd34: ldr             x16, [THR, #0x48]  ; THR::stack_limit
    //     0xe6bd38: cmp             SP, x16
    //     0xe6bd3c: b.ls            #0xe6bed8
    // 0xe6bd40: r1 = Null
    //     0xe6bd40: mov             x1, NULL
    // 0xe6bd44: r2 = 62
    //     0xe6bd44: movz            x2, #0x3e
    // 0xe6bd48: r0 = AllocateArray()
    //     0xe6bd48: bl              #0x10b9c1c  ; AllocateArrayStub
    // 0xe6bd4c: r16 = "LoginParams:{account: "
    //     0xe6bd4c: add             x16, PP, #0x2b, lsl #12  ; [pp+0x2b188] "LoginParams:{account: "
    //     0xe6bd50: ldr             x16, [x16, #0x188]
    // 0xe6bd54: StoreField: r0->field_f = r16
    //     0xe6bd54: stur            w16, [x0, #0xf]
    // 0xe6bd58: ldr             x1, [fp, #0x10]
    // 0xe6bd5c: LoadField: r2 = r1->field_7
    //     0xe6bd5c: ldur            w2, [x1, #7]
    // 0xe6bd60: DecompressPointer r2
    //     0xe6bd60: add             x2, x2, HEAP, lsl #32
    // 0xe6bd64: StoreField: r0->field_13 = r2
    //     0xe6bd64: stur            w2, [x0, #0x13]
    // 0xe6bd68: r16 = ", appType: "
    //     0xe6bd68: add             x16, PP, #0x2b, lsl #12  ; [pp+0x2b190] ", appType: "
    //     0xe6bd6c: ldr             x16, [x16, #0x190]
    // 0xe6bd70: ArrayStore: r0[0] = r16  ; List_4
    //     0xe6bd70: stur            w16, [x0, #0x17]
    // 0xe6bd74: LoadField: r2 = r1->field_b
    //     0xe6bd74: ldur            w2, [x1, #0xb]
    // 0xe6bd78: DecompressPointer r2
    //     0xe6bd78: add             x2, x2, HEAP, lsl #32
    // 0xe6bd7c: StoreField: r0->field_1b = r2
    //     0xe6bd7c: stur            w2, [x0, #0x1b]
    // 0xe6bd80: r16 = ", appVersion: "
    //     0xe6bd80: add             x16, PP, #0x2b, lsl #12  ; [pp+0x2b198] ", appVersion: "
    //     0xe6bd84: ldr             x16, [x16, #0x198]
    // 0xe6bd88: StoreField: r0->field_1f = r16
    //     0xe6bd88: stur            w16, [x0, #0x1f]
    // 0xe6bd8c: LoadField: r2 = r1->field_f
    //     0xe6bd8c: ldur            w2, [x1, #0xf]
    // 0xe6bd90: DecompressPointer r2
    //     0xe6bd90: add             x2, x2, HEAP, lsl #32
    // 0xe6bd94: StoreField: r0->field_23 = r2
    //     0xe6bd94: stur            w2, [x0, #0x23]
    // 0xe6bd98: r16 = ", dateTime: "
    //     0xe6bd98: add             x16, PP, #0x2b, lsl #12  ; [pp+0x2b1a0] ", dateTime: "
    //     0xe6bd9c: ldr             x16, [x16, #0x1a0]
    // 0xe6bda0: StoreField: r0->field_27 = r16
    //     0xe6bda0: stur            w16, [x0, #0x27]
    // 0xe6bda4: LoadField: r2 = r1->field_13
    //     0xe6bda4: ldur            w2, [x1, #0x13]
    // 0xe6bda8: DecompressPointer r2
    //     0xe6bda8: add             x2, x2, HEAP, lsl #32
    // 0xe6bdac: StoreField: r0->field_2b = r2
    //     0xe6bdac: stur            w2, [x0, #0x2b]
    // 0xe6bdb0: r16 = ", language: "
    //     0xe6bdb0: add             x16, PP, #0x2b, lsl #12  ; [pp+0x2b1a8] ", language: "
    //     0xe6bdb4: ldr             x16, [x16, #0x1a8]
    // 0xe6bdb8: StoreField: r0->field_2f = r16
    //     0xe6bdb8: stur            w16, [x0, #0x2f]
    // 0xe6bdbc: ArrayLoad: r2 = r1[0]  ; List_4
    //     0xe6bdbc: ldur            w2, [x1, #0x17]
    // 0xe6bdc0: DecompressPointer r2
    //     0xe6bdc0: add             x2, x2, HEAP, lsl #32
    // 0xe6bdc4: StoreField: r0->field_33 = r2
    //     0xe6bdc4: stur            w2, [x0, #0x33]
    // 0xe6bdc8: r16 = ", md5: "
    //     0xe6bdc8: add             x16, PP, #0x2b, lsl #12  ; [pp+0x2b1b0] ", md5: "
    //     0xe6bdcc: ldr             x16, [x16, #0x1b0]
    // 0xe6bdd0: StoreField: r0->field_37 = r16
    //     0xe6bdd0: stur            w16, [x0, #0x37]
    // 0xe6bdd4: LoadField: r2 = r1->field_1b
    //     0xe6bdd4: ldur            w2, [x1, #0x1b]
    // 0xe6bdd8: DecompressPointer r2
    //     0xe6bdd8: add             x2, x2, HEAP, lsl #32
    // 0xe6bddc: StoreField: r0->field_3b = r2
    //     0xe6bddc: stur            w2, [x0, #0x3b]
    // 0xe6bde0: r16 = ", method: "
    //     0xe6bde0: add             x16, PP, #0x1a, lsl #12  ; [pp+0x1a3a0] ", method: "
    //     0xe6bde4: ldr             x16, [x16, #0x3a0]
    // 0xe6bde8: StoreField: r0->field_3f = r16
    //     0xe6bde8: stur            w16, [x0, #0x3f]
    // 0xe6bdec: LoadField: r2 = r1->field_1f
    //     0xe6bdec: ldur            w2, [x1, #0x1f]
    // 0xe6bdf0: DecompressPointer r2
    //     0xe6bdf0: add             x2, x2, HEAP, lsl #32
    // 0xe6bdf4: StoreField: r0->field_43 = r2
    //     0xe6bdf4: stur            w2, [x0, #0x43]
    // 0xe6bdf8: r16 = ", osType: "
    //     0xe6bdf8: add             x16, PP, #0x2b, lsl #12  ; [pp+0x2b1b8] ", osType: "
    //     0xe6bdfc: ldr             x16, [x16, #0x1b8]
    // 0xe6be00: StoreField: r0->field_47 = r16
    //     0xe6be00: stur            w16, [x0, #0x47]
    // 0xe6be04: LoadField: r2 = r1->field_23
    //     0xe6be04: ldur            w2, [x1, #0x23]
    // 0xe6be08: DecompressPointer r2
    //     0xe6be08: add             x2, x2, HEAP, lsl #32
    // 0xe6be0c: StoreField: r0->field_4b = r2
    //     0xe6be0c: stur            w2, [x0, #0x4b]
    // 0xe6be10: r16 = ", osVersion: "
    //     0xe6be10: add             x16, PP, #0x2b, lsl #12  ; [pp+0x2b1c0] ", osVersion: "
    //     0xe6be14: ldr             x16, [x16, #0x1c0]
    // 0xe6be18: StoreField: r0->field_4f = r16
    //     0xe6be18: stur            w16, [x0, #0x4f]
    // 0xe6be1c: LoadField: r2 = r1->field_27
    //     0xe6be1c: ldur            w2, [x1, #0x27]
    // 0xe6be20: DecompressPointer r2
    //     0xe6be20: add             x2, x2, HEAP, lsl #32
    // 0xe6be24: StoreField: r0->field_53 = r2
    //     0xe6be24: stur            w2, [x0, #0x53]
    // 0xe6be28: r16 = ", password: "
    //     0xe6be28: add             x16, PP, #0x2b, lsl #12  ; [pp+0x2b1c8] ", password: "
    //     0xe6be2c: ldr             x16, [x16, #0x1c8]
    // 0xe6be30: StoreField: r0->field_57 = r16
    //     0xe6be30: stur            w16, [x0, #0x57]
    // 0xe6be34: LoadField: r2 = r1->field_2b
    //     0xe6be34: ldur            w2, [x1, #0x2b]
    // 0xe6be38: DecompressPointer r2
    //     0xe6be38: add             x2, x2, HEAP, lsl #32
    // 0xe6be3c: StoreField: r0->field_5b = r2
    //     0xe6be3c: stur            w2, [x0, #0x5b]
    // 0xe6be40: r16 = ", phoneBrand: "
    //     0xe6be40: add             x16, PP, #0x2b, lsl #12  ; [pp+0x2b1d0] ", phoneBrand: "
    //     0xe6be44: ldr             x16, [x16, #0x1d0]
    // 0xe6be48: StoreField: r0->field_5f = r16
    //     0xe6be48: stur            w16, [x0, #0x5f]
    // 0xe6be4c: LoadField: r2 = r1->field_2f
    //     0xe6be4c: ldur            w2, [x1, #0x2f]
    // 0xe6be50: DecompressPointer r2
    //     0xe6be50: add             x2, x2, HEAP, lsl #32
    // 0xe6be54: StoreField: r0->field_63 = r2
    //     0xe6be54: stur            w2, [x0, #0x63]
    // 0xe6be58: r16 = ", phoneModel: "
    //     0xe6be58: add             x16, PP, #0x2b, lsl #12  ; [pp+0x2b1d8] ", phoneModel: "
    //     0xe6be5c: ldr             x16, [x16, #0x1d8]
    // 0xe6be60: StoreField: r0->field_67 = r16
    //     0xe6be60: stur            w16, [x0, #0x67]
    // 0xe6be64: LoadField: r2 = r1->field_33
    //     0xe6be64: ldur            w2, [x1, #0x33]
    // 0xe6be68: DecompressPointer r2
    //     0xe6be68: add             x2, x2, HEAP, lsl #32
    // 0xe6be6c: StoreField: r0->field_6b = r2
    //     0xe6be6c: stur            w2, [x0, #0x6b]
    // 0xe6be70: r16 = ", timeZone: "
    //     0xe6be70: add             x16, PP, #0x2b, lsl #12  ; [pp+0x2b1e0] ", timeZone: "
    //     0xe6be74: ldr             x16, [x16, #0x1e0]
    // 0xe6be78: StoreField: r0->field_6f = r16
    //     0xe6be78: stur            w16, [x0, #0x6f]
    // 0xe6be7c: LoadField: r2 = r1->field_37
    //     0xe6be7c: ldur            w2, [x1, #0x37]
    // 0xe6be80: DecompressPointer r2
    //     0xe6be80: add             x2, x2, HEAP, lsl #32
    // 0xe6be84: StoreField: r0->field_73 = r2
    //     0xe6be84: stur            w2, [x0, #0x73]
    // 0xe6be88: r16 = ", verifyCode: "
    //     0xe6be88: add             x16, PP, #0x2b, lsl #12  ; [pp+0x2b1e8] ", verifyCode: "
    //     0xe6be8c: ldr             x16, [x16, #0x1e8]
    // 0xe6be90: StoreField: r0->field_77 = r16
    //     0xe6be90: stur            w16, [x0, #0x77]
    // 0xe6be94: LoadField: r2 = r1->field_3b
    //     0xe6be94: ldur            w2, [x1, #0x3b]
    // 0xe6be98: DecompressPointer r2
    //     0xe6be98: add             x2, x2, HEAP, lsl #32
    // 0xe6be9c: StoreField: r0->field_7b = r2
    //     0xe6be9c: stur            w2, [x0, #0x7b]
    // 0xe6bea0: r16 = ", appName: "
    //     0xe6bea0: add             x16, PP, #0x2b, lsl #12  ; [pp+0x2b1f0] ", appName: "
    //     0xe6bea4: ldr             x16, [x16, #0x1f0]
    // 0xe6bea8: StoreField: r0->field_7f = r16
    //     0xe6bea8: stur            w16, [x0, #0x7f]
    // 0xe6beac: LoadField: r2 = r1->field_3f
    //     0xe6beac: ldur            w2, [x1, #0x3f]
    // 0xe6beb0: DecompressPointer r2
    //     0xe6beb0: add             x2, x2, HEAP, lsl #32
    // 0xe6beb4: StoreField: r0->field_83 = r2
    //     0xe6beb4: stur            w2, [x0, #0x83]
    // 0xe6beb8: r16 = "}"
    //     0xe6beb8: add             x16, PP, #0xa, lsl #12  ; [pp+0xa448] "}"
    //     0xe6bebc: ldr             x16, [x16, #0x448]
    // 0xe6bec0: StoreField: r0->field_87 = r16
    //     0xe6bec0: stur            w16, [x0, #0x87]
    // 0xe6bec4: str             x0, [SP]
    // 0xe6bec8: r0 = _interpolate()
    //     0xe6bec8: bl              #0x65b8dc  ; [dart:core] _StringBase::_interpolate
    // 0xe6becc: LeaveFrame
    //     0xe6becc: mov             SP, fp
    //     0xe6bed0: ldp             fp, lr, [SP], #0x10
    // 0xe6bed4: ret
    //     0xe6bed4: ret             
    // 0xe6bed8: r0 = StackOverflowSharedWithoutFPURegs()
    //     0xe6bed8: bl              #0x10b9d24  ; StackOverflowSharedWithoutFPURegsStub
    // 0xe6bedc: b               #0xe6bd40
  }
}
