ROMSize = 131072
Initials = "HB JTC SC DLD PWD KWK LAK SEL B"
ROMDate = "Wed, Nov 6, 1985"
AsmOptions = -sym on,nolines -wb -i :Source:Includes
ToolLibraries = "{Libraries}MacRuntime.o" "{CLibraries}StdCLib.o" ∂
	"{Libraries}IntEnv.o" "{Libraries}Interface.o"

ROMObjects = ∂
	start-init.o ∂
	start-boot.o ∂
	startup-tests.o ∂
	start-error.o ∂
	start-alert.o ∂
	rom-debugger.o ∂
	queue.o ∂
	early-interrupts.o ∂
	vbl-interrupt.o ∂
	mouse-interrupt.o ∂
	vertical-retrace.o ∂
	cursor-core.o ∂
	trap-dispatcher.o ∂
	devicemgr.o ∂
	keyboard.o ∂
	oseventmgr.o ∂
	tfs-dispatch.o ∂
	tfscommon.o ∂
	tfsvol.o ∂
	tfsvol-services.o ∂
	mfsvol.o ∂
	tfsdir1.o ∂
	mfsdir1.o ∂
	tfsdir2.o ∂
	mfsdir2.o ∂
	tfsdir3.o ∂
	mfsdir3.o ∂
	tfsrfn1.o ∂
	mfsrfn1.o ∂
	tfsrfn2.o ∂
	mfsrfn2.o ∂
	tfsrfn3.o ∂
	mfsrfn3.o ∂
	vsm.o ∂
	fxm.o ∂
	cmsvcs.o ∂
	cmmaint.o ∂
	btsvcs.o ∂
	btalloc.o ∂
	btmaint1.o ∂
	btmaint2.o ∂
	cache.o ∂
	cacheio.o ∂
	scsiboot.o ∂
	dispatch-placeholder.o ∂
	lcursor.o ∂
	qdutil.o ∂
	util-extra.o ∂
	grafinit.o ∂
	points.o ∂
	text.o ∂
	drawtext.o ∂
	lines.o ∂
	drawline.o ∂
	putline.o ∂
	rects.o ∂
	bitblt.o ∂
	rgnblt.o ∂
	rrects.o ∂
	ovals.o ∂
	putoval.o ∂
	arcs.o ∂
	drawarc.o ∂
	angles.o ∂
	polygons.o ∂
	regions.o ∂
	seekrgn.o ∂
	rgnop.o ∂
	sortpoints.o ∂
	packrgn.o ∂
	putrgn.o ∂
	bitmaps.o ∂
	stretch.o ∂
	pictures.o ∂
	fontmgr-init.o ∂
	fontmgr-core.o ∂
	fontmgr.o ∂
	segmentloader.o ∂
	sysutil-calls.o ∂
	sysutil.o ∂
	clock.o ∂
	memory-manager.o ∂
	memory-manager-internal.o ∂
	blockmove.o ∂
	toolbox-events.o ∂
	windowmgr.o ∂
	menumgr.o ∂
	controlmgr.o ∂
	resourcemgr.o ∂
	dialogmgr.o ∂
	munger.o ∂
	deskmgr.o ∂
	getmgr.o ∂
	textedit.o ∂
	scrapmgr.o ∂
	packagemgr.o ∂
	sexydate.o ∂
	scsimgr.o ∂
	timemgr.o ∂
	rom-resource-map.o ∂
	print-driver.o ∂
	sound-driver.o ∂
	sony-open.o ∂
	sony-rwt.o ∂
	sony-util.o ∂
	sony-read.o ∂
	sony-write.o ∂
	sony-format.o ∂
	sony-dcd.o ∂
	atp.o ∂
	mpp.o ∂
	serial-driver.o ∂
	standard_mdef.o ∂
	standard_wdef.o ∂
	pack7.o ∂
	pack5.o ∂
	pack4.o ∂
	rom-cursors.o ∂
	rom-fonts.o ∂
	rom_tail.o ∂
	rom-prefix-end.o ∂
	dispatch-table.o ∂
	rom-build-info.o

MacPlus-v3.rebuilt.bin ƒ MacPlus-v3.unfinished.bin hiram :MPW:ROM.make
	Execute DispatchStatus
	hiram -s 128 -i {Initials} -fd {ROMDate} --fill-start {ROMPrefixSize} ∂
		MacPlus-v3.unfinished.bin MacPlus-v3.rebuilt.bin

MacPlus-v3.unfinished.bin ƒ {ROMObjects} rombuild :MPW:ROM.make
	Set DispatchChanged 1
	For DispatchPass In 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16
		If {DispatchChanged} != 0
			Asm {AsmOptions} -i : -o dispatch-placeholder.o :MPW:dispatch-placeholder.a
			Link -t ZROM -rt "ROM =0" -la -o MacPlus-v3.rom {ROMObjects} > MacPlus-v3.map
			rombuild --resolve-layout DispatchSize.a --status-file DispatchStatus ∂
				--rom-size {ROMSize} MacPlus-v3.rom MacPlus-v3.unfinished.bin
			Execute DispatchStatus
		End
	End
	If {DispatchChanged} != 0
		Echo "Dispatch layout did not converge after 16 links"
		Exit 1
	End

DispatchSize.a ƒ
	Echo "DispatchBytes EQU 770" > DispatchSize.a
	SetFile -t TEXT -c "MPS " DispatchSize.a

dispatch-placeholder.o ƒ :MPW:dispatch-placeholder.a DispatchSize.a :MPW:ROM.make
	Asm {AsmOptions} -i : -o {Targ} :MPW:dispatch-placeholder.a

start-init.o ƒ :Source:OS:StartMgr:StartInit.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:StartMgr:StartInit.a'" -o {Targ} :MPW:Asm.a

start-boot.o ƒ :Source:OS:StartMgr:StartBoot.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:StartMgr:StartBoot.a'" -o {Targ} :MPW:Asm.a

startup-tests.o ƒ :Source:OS:StartMgr:StartupTests.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:StartMgr:StartupTests.a'" -o {Targ} :MPW:Asm.a

start-error.o ƒ :Source:OS:StartMgr:StartErr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:StartMgr:StartErr.a'" -o {Targ} :MPW:Asm.a

start-alert.o ƒ :Source:OS:StartMgr:StartAlert.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:StartMgr:StartAlert.a'" -o {Targ} :MPW:Asm.a

rom-debugger.o ƒ :Source:OS:StartMgr:ROMDebugger.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:StartMgr:ROMDebugger.a'" -o {Targ} :MPW:Asm.a

queue.o ƒ :Source:OS:Queue.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:Queue.a'" -o {Targ} :MPW:Asm.a

early-interrupts.o ƒ :Source:OS:EarlyInterrupts.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:EarlyInterrupts.a'" -o {Targ} :MPW:Asm.a

vbl-interrupt.o ƒ :Source:OS:VBLInterrupt.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:VBLInterrupt.a'" -o {Targ} :MPW:Asm.a

mouse-interrupt.o ƒ :Source:OS:MouseInterrupt.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:MouseInterrupt.a'" -o {Targ} :MPW:Asm.a

vertical-retrace.o ƒ :Source:OS:VerticalRetraceMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:VerticalRetraceMgr.a'" -o {Targ} :MPW:Asm.a

cursor-core.o ƒ :Source:OS:CursorCore.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:CursorCore.a'" -o {Targ} :MPW:Asm.a

trap-dispatcher.o ƒ :Source:OS:TrapDispatcher.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:TrapDispatcher.a'" -o {Targ} :MPW:Asm.a

devicemgr.o ƒ :Source:OS:DeviceMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:DeviceMgr.a'" -o {Targ} :MPW:Asm.a

keyboard.o ƒ :Source:OS:Keyboard.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:Keyboard.a'" -o {Targ} :MPW:Asm.a

oseventmgr.o ƒ :Source:OS:OSEventMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:OSEventMgr.a'" -o {Targ} :MPW:Asm.a

tfs-dispatch.o ƒ :Source:OS:HFS:TFS.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:TFS.a'" -o {Targ} :MPW:Asm.a

tfscommon.o ƒ :Source:OS:HFS:TFSCOMMON.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:TFSCOMMON.a'" -o {Targ} :MPW:Asm.a

tfsvol.o ƒ :Source:OS:HFS:TFSVOL.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:TFSVOL.a'" -o {Targ} :MPW:Asm.a

tfsvol-services.o ƒ :Source:OS:HFS:TFSVOLServices.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:TFSVOLServices.a'" -o {Targ} :MPW:Asm.a

mfsvol.o ƒ :Source:OS:HFS:MFSVOL.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:MFSVOL.a'" -o {Targ} :MPW:Asm.a

tfsdir1.o ƒ :Source:OS:HFS:TFSDIR1.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:TFSDIR1.a'" -o {Targ} :MPW:Asm.a

mfsdir1.o ƒ :Source:OS:HFS:MFSDIR1.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:MFSDIR1.a'" -o {Targ} :MPW:Asm.a

tfsdir2.o ƒ :Source:OS:HFS:TFSDIR2.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:TFSDIR2.a'" -o {Targ} :MPW:Asm.a

mfsdir2.o ƒ :Source:OS:HFS:MFSDIR2.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:MFSDIR2.a'" -o {Targ} :MPW:Asm.a

tfsdir3.o ƒ :Source:OS:HFS:TFSDIR3.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:TFSDIR3.a'" -o {Targ} :MPW:Asm.a

mfsdir3.o ƒ :Source:OS:HFS:MFSDIR3.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:MFSDIR3.a'" -o {Targ} :MPW:Asm.a

tfsrfn1.o ƒ :Source:OS:HFS:TFSRFN1.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:TFSRFN1.a'" -o {Targ} :MPW:Asm.a

mfsrfn1.o ƒ :Source:OS:HFS:MFSRFN1.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:MFSRFN1.a'" -o {Targ} :MPW:Asm.a

tfsrfn2.o ƒ :Source:OS:HFS:TFSRFN2.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:TFSRFN2.a'" -o {Targ} :MPW:Asm.a

mfsrfn2.o ƒ :Source:OS:HFS:MFSRFN2.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:MFSRFN2.a'" -o {Targ} :MPW:Asm.a

tfsrfn3.o ƒ :Source:OS:HFS:TFSRFN3.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:TFSRFN3.a'" -o {Targ} :MPW:Asm.a

mfsrfn3.o ƒ :Source:OS:HFS:MFSRFN3.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:MFSRFN3.a'" -o {Targ} :MPW:Asm.a

vsm.o ƒ :Source:OS:HFS:VSM.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:VSM.a'" -o {Targ} :MPW:Asm.a

fxm.o ƒ :Source:OS:HFS:FXM.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:FXM.a'" -o {Targ} :MPW:Asm.a

cmsvcs.o ƒ :Source:OS:HFS:CMSVCS.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:CMSVCS.a'" -o {Targ} :MPW:Asm.a

cmmaint.o ƒ :Source:OS:HFS:CMMAINT.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:CMMAINT.a'" -o {Targ} :MPW:Asm.a

btsvcs.o ƒ :Source:OS:HFS:BTSVCS.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:BTSVCS.a'" -o {Targ} :MPW:Asm.a

btalloc.o ƒ :Source:OS:HFS:BTALLOC.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:BTALLOC.a'" -o {Targ} :MPW:Asm.a

btmaint1.o ƒ :Source:OS:HFS:BTMAINT1.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:BTMAINT1.a'" -o {Targ} :MPW:Asm.a

btmaint2.o ƒ :Source:OS:HFS:BTMAINT2.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:BTMAINT2.a'" -o {Targ} :MPW:Asm.a

cache.o ƒ :Source:OS:HFS:CACHE.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:CACHE.a'" -o {Targ} :MPW:Asm.a

cacheio.o ƒ :Source:OS:HFS:CACHEIO.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:HFS:CACHEIO.a'" -o {Targ} :MPW:Asm.a

scsiboot.o ƒ :Source:OS:SCSIBoot.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:SCSIBoot.a'" -o {Targ} :MPW:Asm.a

dispatch-table.o ƒ :Source:OS:DispTable.a SourceStamp :MPW:Dispatch.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:DispTable.a'" -o {Targ} :MPW:Dispatch.a

lcursor.o ƒ :Source:QuickDraw:LCursor.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:LCursor.a'" -o {Targ} :MPW:Asm.a

qdutil.o ƒ :Source:QuickDraw:QDUtil.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:QDUtil.a'" -o {Targ} :MPW:Asm.a

util-extra.o ƒ :Source:QuickDraw:UtilExtra.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:UtilExtra.a'" -o {Targ} :MPW:Asm.a

grafinit.o ƒ :Source:QuickDraw:GrafInit.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:GrafInit.a'" -o {Targ} :MPW:Asm.a

points.o ƒ :Source:QuickDraw:Points.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:Points.a'" -o {Targ} :MPW:Asm.a

text.o ƒ :Source:QuickDraw:Text.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:Text.a'" -o {Targ} :MPW:Asm.a

drawtext.o ƒ :Source:QuickDraw:DrawText.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:DrawText.a'" -o {Targ} :MPW:Asm.a

lines.o ƒ :Source:QuickDraw:Lines.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:Lines.a'" -o {Targ} :MPW:Asm.a

drawline.o ƒ :Source:QuickDraw:DrawLine.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:DrawLine.a'" -o {Targ} :MPW:Asm.a

putline.o ƒ :Source:QuickDraw:PutLine.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:PutLine.a'" -o {Targ} :MPW:Asm.a

rects.o ƒ :Source:QuickDraw:Rects.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:Rects.a'" -o {Targ} :MPW:Asm.a

bitblt.o ƒ :Source:QuickDraw:BitBlt.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:BitBlt.a'" -o {Targ} :MPW:Asm.a

rgnblt.o ƒ :Source:QuickDraw:RgnBlt.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:RgnBlt.a'" -o {Targ} :MPW:Asm.a

rrects.o ƒ :Source:QuickDraw:RRects.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:RRects.a'" -o {Targ} :MPW:Asm.a

ovals.o ƒ :Source:QuickDraw:Ovals.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:Ovals.a'" -o {Targ} :MPW:Asm.a

putoval.o ƒ :Source:QuickDraw:PutOval.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:PutOval.a'" -o {Targ} :MPW:Asm.a

arcs.o ƒ :Source:QuickDraw:Arcs.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:Arcs.a'" -o {Targ} :MPW:Asm.a

drawarc.o ƒ :Source:QuickDraw:DrawArc.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:DrawArc.a'" -o {Targ} :MPW:Asm.a

angles.o ƒ :Source:QuickDraw:Angles.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:Angles.a'" -o {Targ} :MPW:Asm.a

polygons.o ƒ :Source:QuickDraw:Polygons.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:Polygons.a'" -o {Targ} :MPW:Asm.a

regions.o ƒ :Source:QuickDraw:Regions.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:Regions.a'" -o {Targ} :MPW:Asm.a

seekrgn.o ƒ :Source:QuickDraw:SeekRgn.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:SeekRgn.a'" -o {Targ} :MPW:Asm.a

rgnop.o ƒ :Source:QuickDraw:RgnOp.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:RgnOp.a'" -o {Targ} :MPW:Asm.a

sortpoints.o ƒ :Source:QuickDraw:SortPoints.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:SortPoints.a'" -o {Targ} :MPW:Asm.a

packrgn.o ƒ :Source:QuickDraw:PackRgn.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:PackRgn.a'" -o {Targ} :MPW:Asm.a

putrgn.o ƒ :Source:QuickDraw:PutRgn.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:PutRgn.a'" -o {Targ} :MPW:Asm.a

bitmaps.o ƒ :Source:QuickDraw:Bitmaps.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:Bitmaps.a'" -o {Targ} :MPW:Asm.a

stretch.o ƒ :Source:QuickDraw:Stretch.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:Stretch.a'" -o {Targ} :MPW:Asm.a

pictures.o ƒ :Source:QuickDraw:Pictures.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:QuickDraw:Pictures.a'" -o {Targ} :MPW:Asm.a

fontmgr-init.o ƒ :Source:Toolbox:FontMgrInit.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:FontMgrInit.a'" -o {Targ} :MPW:Asm.a

fontmgr-core.o ƒ :Source:Toolbox:FontMgrCore.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:FontMgrCore.a'" -o {Targ} :MPW:Asm.a

fontmgr.o ƒ :Source:Toolbox:FontMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:FontMgr.a'" -o {Targ} :MPW:Asm.a

segmentloader.o ƒ :Source:Toolbox:SegmentLoader.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:SegmentLoader.a'" -o {Targ} :MPW:Asm.a

sysutil-calls.o ƒ :Source:OS:SysUtilCalls.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:SysUtilCalls.a'" -o {Targ} :MPW:Asm.a

sysutil.o ƒ :Source:OS:SysUtil.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:SysUtil.a'" -o {Targ} :MPW:Asm.a

clock.o ƒ :Source:OS:Clock.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:Clock.a'" -o {Targ} :MPW:Asm.a

memory-manager.o ƒ :Source:OS:MemoryMgr:MemoryMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:MemoryMgr:MemoryMgr.a'" -o {Targ} :MPW:Asm.a

memory-manager-internal.o ƒ :Source:OS:MemoryMgr:MemoryMgrInternal.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:MemoryMgr:MemoryMgrInternal.a'" -o {Targ} :MPW:Asm.a

blockmove.o ƒ :Source:OS:MemoryMgr:BlockMove.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:MemoryMgr:BlockMove.a'" -o {Targ} :MPW:Asm.a

toolbox-events.o ƒ :Source:Toolbox:ToolboxEventMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:ToolboxEventMgr.a'" -o {Targ} :MPW:Asm.a

windowmgr.o ƒ :Source:Toolbox:WindowMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:WindowMgr.a'" -o {Targ} :MPW:Asm.a

menumgr.o ƒ :Source:Toolbox:MenuMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:MenuMgr.a'" -o {Targ} :MPW:Asm.a

controlmgr.o ƒ :Source:Toolbox:ControlMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:ControlMgr.a'" -o {Targ} :MPW:Asm.a

resourcemgr.o ƒ :Source:Toolbox:ResourceMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:ResourceMgr.a'" -o {Targ} :MPW:Asm.a

dialogmgr.o ƒ :Source:Toolbox:DialogMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:DialogMgr.a'" -o {Targ} :MPW:Asm.a

munger.o ƒ :Source:Toolbox:Munger.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:Munger.a'" -o {Targ} :MPW:Asm.a

deskmgr.o ƒ :Source:Toolbox:DeskMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:DeskMgr.a'" -o {Targ} :MPW:Asm.a

getmgr.o ƒ :Source:Toolbox:GetMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:GetMgr.a'" -o {Targ} :MPW:Asm.a

textedit.o ƒ :Source:Toolbox:TextEdit.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:TextEdit.a'" -o {Targ} :MPW:Asm.a

scrapmgr.o ƒ :Source:Toolbox:ScrapMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:ScrapMgr.a'" -o {Targ} :MPW:Asm.a

packagemgr.o ƒ :Source:Toolbox:PackageMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:PackageMgr.a'" -o {Targ} :MPW:Asm.a

sexydate.o ƒ :Source:Toolbox:SexyDate.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Toolbox:SexyDate.a'" -o {Targ} :MPW:Asm.a

scsimgr.o ƒ :Source:OS:SCSIMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:SCSIMgr.a'" -o {Targ} :MPW:Asm.a

timemgr.o ƒ :Source:OS:TimeMgr.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:OS:TimeMgr.a'" -o {Targ} :MPW:Asm.a

rom-resource-map.o ƒ :Source:Resources:ROMResourceMap.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:ROMResourceMap.a'" -o {Targ} :MPW:Asm.a

print-driver.o ƒ :Source:Resources:PrintDriver.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:PrintDriver.a'" -o {Targ} :MPW:Asm.a

sound-driver.o ƒ :Source:Resources:SoundDriver.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:SoundDriver.a'" -o {Targ} :MPW:Asm.a

sony-open.o ƒ :Source:Resources:Sony:Sony.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:Sony:Sony.a'" -o {Targ} :MPW:Asm.a

sony-rwt.o ƒ :Source:Resources:Sony:SonyRWT.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:Sony:SonyRWT.a'" -o {Targ} :MPW:Asm.a

sony-util.o ƒ :Source:Resources:Sony:SonyUtil.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:Sony:SonyUtil.a'" -o {Targ} :MPW:Asm.a

sony-read.o ƒ :Source:Resources:Sony:SonyRead.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:Sony:SonyRead.a'" -o {Targ} :MPW:Asm.a

sony-write.o ƒ :Source:Resources:Sony:SonyWrite.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:Sony:SonyWrite.a'" -o {Targ} :MPW:Asm.a

sony-format.o ƒ :Source:Resources:Sony:SonyFormat.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:Sony:SonyFormat.a'" -o {Targ} :MPW:Asm.a

sony-dcd.o ƒ :Source:Resources:Sony:SonyDCD.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:Sony:SonyDCD.a'" -o {Targ} :MPW:Asm.a

atp.o ƒ :Source:Resources:ATP.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:ATP.a'" -o {Targ} :MPW:Asm.a

mpp.o ƒ :Source:Resources:MPP.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:MPP.a'" -o {Targ} :MPW:Asm.a

serial-driver.o ƒ :Source:Resources:Serial:SerialDriver.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:Serial:SerialDriver.a'" -o {Targ} :MPW:Asm.a

standard_mdef.o ƒ :Source:Resources:StandardMDEF.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:StandardMDEF.a'" -o {Targ} :MPW:Asm.a

standard_wdef.o ƒ :Source:Resources:StandardWDEF.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:StandardWDEF.a'" -o {Targ} :MPW:Asm.a

pack7.o ƒ :Source:Resources:SANE:BinDec.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:SANE:BinDec.a'" -o {Targ} :MPW:Asm.a

pack5.o ƒ :Source:Resources:SANE:Elems68K.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:SANE:Elems68K.a'" -o {Targ} :MPW:Asm.a

pack4.o ƒ :Source:Resources:SANE:FP68K.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:Resources:SANE:FP68K.a'" -o {Targ} :MPW:Asm.a

rom-cursors.o ƒ rom-cursors.a :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':rom-cursors.a'" -o {Targ} :MPW:Asm.a

rom-fonts.o ƒ rom-fonts.a :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':rom-fonts.a'" -o {Targ} :MPW:Asm.a

rom_tail.o ƒ :Source:ROMTail.a SourceStamp :MPW:Asm.a :MPW:Asm.a :MPW:ROM.make
	Asm {AsmOptions} -d "&SourceFile=':Source:ROMTail.a'" -o {Targ} :MPW:Asm.a

rom-prefix-end.o ƒ :MPW:rom-prefix-end.a :MPW:ROM.make
	Asm {AsmOptions} -o {Targ} :MPW:rom-prefix-end.a

rom-build-info.o ƒ :MPW:rom-build-info.a :MPW:ROM.make
	Asm {AsmOptions} -o {Targ} :MPW:rom-build-info.a

rom-cursors.rsrc ƒ :Source:Resources:Cursors.r :MPW:ROM.make
	Rez :Source:Resources:Cursors.r -o {Targ}

rom-cursors.a ƒ rom-cursors.rsrc :MPW:rom-cursors.layout rombuild :MPW:ROM.make
	rombuild --resources :MPW:rom-cursors.layout rom-cursors.rsrc {Targ}

rom-fonts.rsrc ƒ :Source:Resources:SystemFonts.r :MPW:ROM.make
	Rez :Source:Resources:SystemFonts.r -o {Targ}

rom-fonts.a ƒ rom-fonts.rsrc :MPW:rom-fonts.layout rombuild :MPW:ROM.make
	rombuild --resources :MPW:rom-fonts.layout rom-fonts.rsrc {Targ}

rombuild.c.o ƒ :Tools:rombuild.c :MPW:ROM.make
	SC :Tools:rombuild.c -o {Targ} -w iserror

rombuild ƒ rombuild.c.o {ToolLibraries} :MPW:ROM.make
	Link -c "MPS " -t MPST -o {Targ} rombuild.c.o {ToolLibraries}

hiram.c.o ƒ :Tools:hiram.c :MPW:ROM.make
	SC :Tools:hiram.c -o {Targ} -w iserror

hiram ƒ hiram.c.o {ToolLibraries} :MPW:ROM.make
	Link -c "MPS " -t MPST -o {Targ} hiram.c.o {ToolLibraries}
