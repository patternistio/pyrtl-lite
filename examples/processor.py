from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pyrtlite import * 

NOP  = 0x00     # NOP
LDI  = 0x10     # LDI imm  : A <- imm
LDA  = 0x11     # LDA addr : A <- MEM[addr]
STA  = 0x12     # STA addr : MEM[addr] <- A
ADDI = 0x20     # ADDI imm : A <- A + imm
ADD  = 0x21     # ADD addr : A <- A + MEM
SUBI = 0x22     # SUBI imm : A <- A - imm
JMP  = 0x30     # JMP addr : PC <- addr
JZ   = 0x31     # JZ  addr : PC <- addr if z
JNZ  = 0x32     # JNZ addr : PC <- addr if not z
HALT = 0xFF     # HALT

class Processor(Module): 
    def build(self): 
        self.mem = Mem(256, init = 0)
        self.pc  = Reg(0)
        self.a   = Reg(0)
        self.z   = Reg(True)
        self.h   = Reg(False)

    def logic(self): 
        opcode    = self.mem[self.pc]
        next_byte = self.pc + 1
        operand   = self.mem[next_byte]

        self.pc <<= (self.pc + 1) & 0xFF
        self.a  <<= self.a & 0xFF
        self.z  <<= self.z
        self.h  <<= self.h

        if not self.h: 
            if opcode == NOP: 
                pass
            elif opcode == LDI: 
                self.a  <<= operand
                self.pc <<= (self.pc + 2) & 0xFF
                self.z  <<= True if operand == 0 else False
            elif opcode == LDA:
                acc = self.mem[operand] 
                self.a  <<= acc
                self.pc <<= (self.pc + 2) & 0xFF
                self.z  <<= True if acc == 0 else False
            elif opcode == STA: 

                self.mem[operand] <<= self.a
                self.pc <<= (self.pc + 2) & 0xFF
            elif opcode == ADDI: 
                acc = (self.a + operand) & 0xFF
                self.a  <<= acc
                self.pc <<= (self.pc + 2) & 0xFF
                self.z  <<= True if acc == 0 else False
            elif opcode == ADD: 
                acc = (self.a + self.mem[operand]) & 0xFF
                self.a  <<= acc
                self.pc <<= (self.pc + 2) & 0xFF
                self.z  <<= True if acc == 0 else False
            elif opcode == SUBI: 
                acc = (self.a - operand) & 0xFF
                self.a  <<= acc
                self.pc <<= (self.pc + 2) & 0xFF
                self.z  <<= True if acc == 0 else False
            elif opcode == JMP: 
                self.pc <<= operand
            elif opcode == JZ:
                self.pc <<= operand if self.z else (self.pc + 2) & 0xFF
            elif opcode == JNZ: 
                self.pc <<= operand if not self.z else (self.pc + 2) & 0xFF
            elif opcode == HALT: 
                self.h  <<= True
            else: 
                self.h  <<= True

def load(cpu, program, start = 0): 
    for i, byte in enumerate(program): 
        addr = (start + i) & 0xFF
        cpu.mem[addr].value = byte & 0xFF
        cpu.mem[addr].init = byte & 0xFF

def run(program, max = 200, trace = False): 
    cpu = Processor()
    load(cpu, program)    

    sim = Sim(cpu)

    for cycle in range(max):
        if sim.peek(cpu.h):
            break
        sim.step(trace = trace)
        if trace: 
            print(f"  [cpu state]")
            print(f"    cycle = {cycle:03d}, pc = {sim.peek(cpu.pc):02X}")
            print(f"    a = {sim.peek(cpu.a):02X}, z = {sim.peek(cpu.z)}, h = {sim.peek(cpu.h)}")
    

    return cpu, sim

if __name__ == "__main__": 
    # adds numbers from 1 to 5
    program = [
        LDI,  0x05, 
        STA,  0xF0, 

        LDI,  0x00, 
        STA,  0xF1, 
        
        LDA,  0xF1, 
        ADD,  0xF0, 
        STA,  0xF1, 
        
        LDA,  0xF0, 
        SUBI, 0x01, 
        STA,  0xF0, 
        JNZ,  0x08, 
        
        HALT
    ]

    cpu, sim = run(program, trace = False)

    print("Program Completed")
    print(f"MEM[F0] (index) = {sim.peek(cpu.mem.read(0xF0))}")
    print(f"MEM[F1] (sum)   = {sim.peek(cpu.mem.read(0xF1))}")