import ghidra.app.script.GhidraScript;
import ghidra.program.model.symbol.*;
public class ExportMacPlusSymbols extends GhidraScript {
    public void run() throws Exception {
        SymbolIterator symbols = currentProgram.getSymbolTable().getAllSymbols(true);
        while (symbols.hasNext()) {
            Symbol symbol = symbols.next();
            println(symbol.getAddress() + "\t" + symbol.getName(true) + "\t" + symbol.getSymbolType() + "\t" + symbol.getSource());
        }
    }
}
