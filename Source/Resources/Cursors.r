/* Reconstruction: This excerpt preserves the four cursor resources from
   Resources/ROMFonts.r. Their data matches the Mac Plus ROM unchanged.
   The header and history below describe the released source file. */

/*
	File:		ROMFonts.r

	Contains:	xxx put contents here (or delete the whole line) xxx

	Written by:	xxx put name of writer here (or delete the whole line) xxx

	Copyright:	© 1989-1993 by Apple Computer, Inc., all rights reserved.

	Change History (most recent first):

	   <SM4>	 9/13/93	RC		fixed bug with FONDs being called FONTs.
	   <SM3>	 7/14/93	joe
	   <SM2>	 5/30/93	joe		On PDM, use a sampled version of Simple Beep.
	   <SM2>	11/20/92	RB		Updated the system default beep.
	   <1.1>	 5/23/89	CCH		Finally got rid of that dumb EASE resource!!
	   <1.0>	 5/16/89	CCH		Adding from ROMFonts.rsrc. This is a text version, which is
									easier to keep track of for SCM.

*/

/*EASE$$$ READ ONLY COPY of file “ROMFonts.r”
** 1.1	CCH 05/23/1989 Finally got rid of that dumb EASE resource!! 
** 1.0	CCH 05/16/1989 Adding from ROMFonts.rsrc. This is a text
**		version, which is easier to keep track of for SCM.
** END EASE MODIFICATION HISTORY */

data 'CURS' (4, sysheap, locked) {
	$"3F 00 3F 00 3F 00 3F 00 40 80 84 40 84 40 84 60"    /* ?.?.?.?.@ÄÑ@Ñ@Ñ` */
	$"9C 60 80 40 80 40 40 80 3F 00 3F 00 3F 00 3F 00"    /* ú`Ä@Ä@@Ä?.?.?.?. */
	$"3F 00 3F 00 3F 00 3F 00 7F 80 FF C0 FF C0 FF C0"    /* ?.?.?.?..Ä.¿.¿.¿ */
	$"FF C0 FF C0 FF C0 7F 80 3F 00 3F 00 3F 00 3F 00"    /* .¿.¿.¿.Ä?.?.?.?. */
	$"00 08 00 08"                                        /* .... */
};

data 'CURS' (1, sysheap, locked) {
	$"0C 60 02 80 01 00 01 00 01 00 01 00 01 00 01 00"    /* .`.Ä............ */
	$"01 00 01 00 01 00 01 00 01 00 01 00 02 80 0C 60"    /* .............Ä.` */
	$"00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"    /* ................ */
	$"00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"    /* ................ */
	$"00 04 00 07"                                        /* .... */
};

data 'CURS' (3, sysheap, locked) {
	$"00 00 07 C0 04 60 04 60 04 60 7C 7C 43 86 42 86"    /* ...¿.`.`.`||CÜBÜ */
	$"43 86 7C 7E 3C 7E 04 60 04 60 07 E0 03 E0 00 00"    /* CÜ|~<~.`.`...... */
	$"0F C0 0F E0 0F F0 0F F0 FF FF FF FE FC 7F FC 7F"    /* .¿.............. */
	$"FC 7F FF FF 7F FF 7F FF 0F F0 0F F0 07 F0 03 E0"    /* ................ */
	$"00 08 00 08"                                        /* .... */
};

data 'CURS' (2, sysheap, locked) {
	$"04 00 04 00 04 00 04 00 04 00 FF E0 04 00 04 00"    /* ................ */
	$"04 00 04 00 04 00 04 00 00 00 00 00 00 00 00 00"    /* ................ */
	$"00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"    /* ................ */
	$"00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"    /* ................ */
	$"00 05 00 05"                                        /* .... */
};
