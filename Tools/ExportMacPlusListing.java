import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.CodeUnit;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

public class ExportMacPlusListing extends GhidraScript {
    private String encode(String value) {
        if (value == null) return "";
        return Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8));
    }

    public void run() throws Exception {
        AddressSet rom = new AddressSet(toAddr(0x400000), toAddr(0x41ffff));
        InstructionIterator instructions = currentProgram.getListing().getInstructions(rom, true);
        while (instructions.hasNext()) {
            Instruction instruction = instructions.next();
            StringBuilder hex = new StringBuilder();
            for (byte value : instruction.getBytes()) hex.append(String.format("%02x", value & 0xff));
            println("ROM_INSTRUCTION\t" + instruction.getAddress() + "\t" + hex + "\t" + encode(instruction.toString()));
        }
        for (CodeUnit unit : currentProgram.getListing().getCodeUnits(rom, true)) {
            for (int type = 0; type <= 4; type++) {
                String comment = unit.getComment(type);
                if (comment != null) println("ROM_COMMENT\t" + unit.getAddress() + "\t" + type + "\t" + encode(comment));
            }
        }
    }
}
