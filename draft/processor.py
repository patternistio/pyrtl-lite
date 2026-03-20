from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pyrtlite import * 


# Opcodes (8-bit)
NOP  = 0x00
LDI  = 0x10  # LDI imm: A <- imm
LDA  = 0x11  # LDA addr: A <- MEM[addr]
STA  = 0x12  # STA addr: MEM[addr] <- A
ADDI = 0x20  # ADDI imm: A <- A + imm
ADD  = 0x21  # ADD addr: A <- A + MEM[addr]
SUBI = 0x22  # SUBI imm: A <- A - imm
JMP  = 0x30  # JMP addr
JZ   = 0x31  # JZ addr
JNZ  = 0x32  # JNZ addr
HALT = 0xFF


class Processor(Module):

	def build(self):
		self.mem = Mem(256, init=0)
		self.pc = Reg(0)
		self.a = Reg(0)
		self.zero = Reg(1)
		self.halted = Reg(0)

		self.out_pc = Out(0)
		self.out_a = Out(0)
		self.out_zero = Out(0)
		self.out_halted = Out(0)

	def logic(self):
		pc = int(self.pc) & 0xFF
		a = int(self.a) & 0xFF
		z = int(self.zero)
		halted = int(self.halted)

		opcode = int(self.mem[pc]) & 0xFF
		next_byte_addr = (pc + 1) & 0xFF
		operand = int(self.mem[next_byte_addr]) & 0xFF

		self.pc <<= (pc + 1) & 0xFF
		self.a <<= a
		self.zero <<= z
		self.halted <<= halted

		if not halted:
			if opcode == NOP:
				pass
			elif opcode == LDI:
				self.a <<= operand
				self.pc <<= (pc + 2) & 0xFF
				self.zero <<= 1 if operand == 0 else 0
			elif opcode == LDA:
				loaded = int(self.mem[operand]) & 0xFF
				self.a <<= loaded
				self.pc <<= (pc + 2) & 0xFF
				self.zero <<= 1 if loaded == 0 else 0
			elif opcode == STA:
				self.mem[operand] <<= a
				self.pc <<= (pc + 2) & 0xFF
			elif opcode == ADDI:
				acc = (a + operand) & 0xFF
				self.a <<= acc
				self.pc <<= (pc + 2) & 0xFF
				self.zero <<= 1 if acc == 0 else 0
			elif opcode == ADD:
				acc = (a + (int(self.mem[operand]) & 0xFF)) & 0xFF
				self.a <<= acc
				self.pc <<= (pc + 2) & 0xFF
				self.zero <<= 1 if acc == 0 else 0
			elif opcode == SUBI:
				acc = (a - operand) & 0xFF
				self.a <<= acc
				self.pc <<= (pc + 2) & 0xFF
				self.zero <<= 1 if acc == 0 else 0
			elif opcode == JMP:
				self.pc <<= operand
			elif opcode == JZ:
				self.pc <<= operand if z == 1 else (pc + 2) & 0xFF
			elif opcode == JNZ:
				self.pc <<= operand if z == 0 else (pc + 2) & 0xFF
			elif opcode == HALT:
				self.halted <<= 1
			else:
				self.halted <<= 1

		self.out_pc @= self.pc
		self.out_a @= self.a
		self.out_zero @= self.zero
		self.out_halted @= self.halted


def load_program(cpu, program, start_addr=0):
	for i, byte in enumerate(program):
		cpu.mem.cells[(start_addr + i) & 0xFF].value = byte & 0xFF


def run_program(program, max_cycles=200, trace=False):
	cpu = Processor()
	load_program(cpu, program)
	sim = Sim(cpu)

	for cycle in range(max_cycles):
		if sim.peek(cpu.halted):
			break
		sim.step(trace=trace)
		if trace:
			print(
				f"cycle={cycle:03d} pc={sim.peek(cpu.pc):02X} "
				f"a={sim.peek(cpu.a):02X} z={sim.peek(cpu.zero)}"
			)

	return cpu, sim


if __name__ == "__main__":
	# Program: sum 1 + 2 + 3 + 4 + 5 into MEM[0xF0].
	# Uses MEM[0xF1] as loop counter.
	#
	# 00: LDI 0
	# 02: STA F0
	# 04: LDI 5
	# 06: STA F1
	# 08: LDA F0   ; loop:
	# 0A: ADD F1
	# 0C: STA F0
	# 0E: LDA F1
	# 10: SUBI 1
	# 12: STA F1
	# 14: JNZ 08
	# 16: HALT
	program = [
		LDI, 0x00,
		STA, 0xF0,
		LDI, 0x05,
		STA, 0xF1,
		LDA, 0xF0,
		ADD, 0xF1,
		STA, 0xF0,
		LDA, 0xF1,
		SUBI, 0x01,
		STA, 0xF1,
		JNZ, 0x08,
		HALT,
	]

	cpu, sim = run_program(program, trace=False)

	result = sim.peek(cpu.mem.cells[0xF0])
	counter = sim.peek(cpu.mem.cells[0xF1])

	print("Processor finished")
	print(f"A={sim.peek(cpu.a)} PC={sim.peek(cpu.pc)} Z={sim.peek(cpu.zero)} HALTED={sim.peek(cpu.halted)}")
	print(f"MEM[F0] (sum) = {result}")
	print(f"MEM[F1] (counter) = {counter}")