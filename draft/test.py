import io
import unittest
from contextlib import redirect_stdout

from sim import (
	Bundle,
	Const,
	In,
	Mem,
	Module,
	Mux,
	Op,
	Out,
	Reg,
	Signal,
	Sim,
	UnaryOp,
	Vec,
	Wire,
	_collect,
	_lift,
	peek,
	poke,
)


class CombChain(Module):
	def build(self):
		self.src = In(0)
		self.mid = Wire(0)
		self.out = Out(0)

	def logic(self):
		self.mid @= self.src + 2
		self.out @= self.mid * 3


class RegisterStage(Module):
	def build(self):
		self.enable = In(False)
		self.inc = In(0)
		self.state = Reg(0)
		self.out = Out(0)

	def logic(self):
		self.state <<= Mux(self.enable, self.state + self.inc, self.state)
		self.out @= self.state


class ChildAdder(Module):
	def build(self):
		self.left = In(0)
		self.right = In(0)
		self.out = Out(0)

	def logic(self):
		self.out @= self.left + self.right


class HierarchicalSystem(Module):
	def build(self):
		self.bias = In(0)
		self.children = Vec(2, ChildAdder())
		self.pipes = Vec(2, Reg(0))
		self.total = Out(0)

	def logic(self):
		self.children[0].left @= self.pipes[0]
		self.children[0].right @= self.bias
		self.children[1].left @= self.children[0].out
		self.children[1].right @= 1
		self.pipes[0] <<= self.pipes[0] + 1
		self.pipes[1] <<= self.children[1].out
		self.total @= self.pipes[1]


class Oscillator(Module):
	def build(self):
		self.a = Wire(0)
		self.b = Wire(1)

	def logic(self):
		self.a @= self.b + 1
		self.b @= self.a + 1


class ShiftAddMultiplier(Module):
	def build(self, width=8):
		self.width = width
		self.start = In(False)
		self.multiplicand = In(0)
		self.multiplier = In(0)
		self.a = Reg(0)
		self.b = Reg(0)
		self.product = Reg(0)
		self.count = Reg(0)
		self.busy = Reg(False)
		self.done = Out(False)
		self.result = Out(0)

	def logic(self):
		if self.start and not self.busy:
			self.a <<= self.multiplicand
			self.b <<= self.multiplier
			self.product <<= 0
			self.count <<= self.width
			self.busy <<= True
		elif self.busy:
			self.product <<= self.product + Mux(self.b % 2 == 1, self.a, 0)
			self.a <<= self.a * 2
			self.b <<= self.b // 2
			self.count <<= self.count - 1
			self.busy <<= self.count > 1
		else:
			self.a <<= self.a
			self.b <<= self.b
			self.product <<= self.product
			self.count <<= self.count
			self.busy <<= self.busy

		self.done @= self.busy == False
		self.result @= self.product


class SequenceDetector1011(Module):
	def build(self):
		self.bit_in = In(0)
		self.state = Reg(0)
		self.match_reg = Reg(False)
		self.match_count = Reg(0)
		self.match = Out(False)

	def logic(self):
		bit = int(self.bit_in)
		state = int(self.state)

		if state == 0:
			next_state = 1 if bit == 1 else 0
		elif state == 1:
			next_state = 1 if bit == 1 else 2
		elif state == 2:
			next_state = 3 if bit == 1 else 0
		else:
			next_state = 1 if bit == 1 else 2

		detect = (self.state == 3) & (self.bit_in == 1)
		self.state <<= next_state
		self.match_reg <<= detect
		self.match_count <<= Mux(detect, self.match_count + 1, self.match_count)
		self.match @= self.match_reg


class FourTapFilter(Module):
	def build(self):
		self.enable = In(True)
		self.sample = In(0)
		self.delay = Vec(4, Reg(0))
		self.filtered = Out(0)

	def logic(self):
		if self.enable:
			self.delay[0] <<= self.sample
			self.delay[1] <<= self.delay[0]
			self.delay[2] <<= self.delay[1]
			self.delay[3] <<= self.delay[2]
		else:
			for stage in self.delay:
				stage <<= stage

		self.filtered @= (
			self.delay[0]
			+ self.delay[1] * 2
			+ self.delay[2] * 3
			+ self.delay[3] * 4
		)


class MiniProcessor(Module):
	def build(self, program, reg_count=8, data_words=4):
		self.program = list(program)
		self.regs = Vec(reg_count, Reg(0))
		self.data = Vec(data_words, Reg(0))
		self.pc = Reg(0)
		self.halted = Reg(False)
		self.retired = Reg(0)
		self.pc_out = Out(0)
		self.halted_out = Out(False)
		self.acc_out = Out(0)

	def logic(self):
		if self.halted:
			self.halted <<= self.halted
			self.pc <<= self.pc
			self.retired <<= self.retired
		else:
			pc = int(self.pc)
			if 0 <= pc < len(self.program):
				inst = self.program[pc]
				op = inst[0]
				self.pc <<= self.pc + 1
				self.retired <<= self.retired + 1
				self.halted <<= False

				if op == "LOADI":
					_, rd, imm = inst
					self.regs[rd] <<= imm
				elif op == "LOAD":
					_, rd, addr = inst
					self.regs[rd] <<= self.data[addr]
				elif op == "STORE":
					_, rs, addr = inst
					self.data[addr] <<= self.regs[rs].nxt
				elif op == "ADD":
					_, rd, rs = inst
					self.regs[rd] <<= self.regs[rd] + self.regs[rs]
				elif op == "ADDI":
					_, rd, imm = inst
					self.regs[rd] <<= self.regs[rd] + imm
				elif op == "SUBI":
					_, rd, imm = inst
					self.regs[rd] <<= self.regs[rd] - imm
				elif op == "JNZ":
					_, rs, target = inst
					if self.regs[rs]:
						self.pc.set_next(target, overwrite=True)
				elif op == "JMP":
					_, target = inst
					self.pc.set_next(target, overwrite=True)
				elif op == "HALT":
					self.halted.set_next(True, overwrite=True)
				else:
					raise ValueError(f"unknown opcode {op}")
			else:
				self.halted <<= True
				self.pc <<= self.pc
				self.retired <<= self.retired
		self.pc_out @= self.pc
		self.halted_out @= self.halted
		self.acc_out @= self.regs[0]


class PipelinedMiniProcessor(Module):
	def build(self, program, reg_count=8, data_words=4):
		self.program = list(program)
		self.regs = Vec(reg_count, Reg(0))
		self.data = Vec(data_words, Reg(0))
		self.fetch_pc = Reg(0)
		self.if_valid = Reg(False)
		self.if_pc = Reg(0)
		self.if_inst = Reg(("NOP",))
		self.id_valid = Reg(False)
		self.id_pc = Reg(0)
		self.id_inst = Reg(("NOP",))
		self.halted = Reg(False)
		self.retired = Reg(0)
		self.fetch_pc_out = Out(-1)
		self.decode_pc_out = Out(-1)
		self.decode_op_out = Out("NOP")
		self.acc_out = Out(0)
		self.halted_out = Out(False)

	def logic(self):
		branch_target = None

		if self.halted:
			self.fetch_pc <<= self.fetch_pc
			self.if_valid <<= False
			self.if_pc <<= self.if_pc
			self.if_inst <<= ("NOP",)
			self.id_valid <<= False
			self.id_pc <<= self.id_pc
			self.id_inst <<= ("NOP",)
			self.halted <<= True
			self.retired <<= self.retired
		else:
			if self.id_valid:
				inst = self.id_inst.eval()
				op = inst[0]
				self.retired <<= self.retired + 1

				match op:
					case "NOP":
						pass
					case "LOADI":
						_, rd, imm = inst
						self.regs[rd] <<= imm
					case "LOAD":
						_, rd, addr = inst
						self.regs[rd] <<= self.data[addr]
					case "STORE":
						_, rs, addr = inst
						self.data[addr] <<= self.regs[rs].nxt
					case "ADD":
						_, rd, rs = inst
						self.regs[rd] <<= self.regs[rd] + self.regs[rs]
					case "ADDI":
						_, rd, imm = inst
						self.regs[rd] <<= self.regs[rd] + imm
					case "BZ":
						_, rs, target = inst
						if not self.regs[rs]:
							branch_target = target
					case "HALT":
						self.halted <<= True
					case _:
						raise ValueError(f"unknown opcode {op}")
			else:
				self.retired <<= self.retired

			if self.halted.nxt:
				self.fetch_pc <<= self.fetch_pc
				self.if_valid <<= False
				self.if_pc <<= self.if_pc
				self.if_inst <<= ("NOP",)
				self.id_valid <<= False
				self.id_pc <<= self.id_pc
				self.id_inst <<= ("NOP",)
			elif branch_target is not None:
				self.id_valid <<= False
				self.id_pc <<= 0
				self.id_inst <<= ("NOP",)
				if 0 <= branch_target < len(self.program):
					self.if_valid <<= True
					self.if_pc <<= branch_target
					self.if_inst <<= self.program[branch_target]
					self.fetch_pc <<= branch_target + 1
				else:
					self.if_valid <<= False
					self.if_pc <<= branch_target
					self.if_inst <<= ("NOP",)
					self.fetch_pc <<= branch_target
					self.halted.set_next(True, overwrite=True)
			else:
				self.id_valid <<= self.if_valid
				self.id_pc <<= self.if_pc
				self.id_inst <<= self.if_inst.eval()
				if 0 <= int(self.fetch_pc) < len(self.program):
					self.if_valid <<= True
					self.if_pc <<= self.fetch_pc
					self.if_inst <<= self.program[int(self.fetch_pc)]
					self.fetch_pc <<= self.fetch_pc + 1
				else:
					self.if_valid <<= False
					self.if_pc <<= self.fetch_pc
					self.if_inst <<= ("NOP",)

			if self.halted.next_src is None:
				self.halted <<= False
		self.fetch_pc_out @= self.if_pc if self.if_valid else -1
		self.decode_pc_out @= self.id_pc if self.id_valid else -1
		self.decode_op_out @= self.id_inst.eval()[0] if self.id_valid else "NOP"
		self.acc_out @= self.regs[0]
		self.halted_out @= self.halted


class InlineBranchStage(Module):
	def build(self):
		self.redirect = In(False)
		self.target = In(0)
		self.pc = Reg(0)
		self.decode_pc = Reg(0)
		self.out = Out(0)

	def logic(self):
		self.pc <<= self.pc + 1
		if self.redirect:
			self.pc.set_next(self.target, overwrite=True)
		self.decode_pc <<= self.pc.nxt
		self.out @= self.decode_pc


class BundleMemoryStage(Module):
	def build(self):
		self.req = Bundle()
		self.req.addr = In(0)
		self.req.data = In(0)
		self.req.write = In(False)
		self.resp = Bundle()
		self.resp.data = Out(0)
		self.resp.mirror = Out(0)
		self.mem = Mem(4, init=0)

	def logic(self):
		if self.req.write:
			self.mem.write(self.req.addr, self.req.data)
		self.resp.data @= self.mem.read(self.req.addr)
		self.resp.mirror @= self.mem.cells[1]


class GuardedCounter(Module):
	def build(self):
		self.enable = In(False)
		self.limit = In(0)
		self.count = Reg(0)
		self.out = Out(0)

	def logic(self):
		if self.enable:
			self.count <<= self.count + 1
		else:
			self.count <<= self.count
		self.Assert(self.count.nxt <= self.limit, "count overflow")
		self.out @= self.count


class ExpressionTests(unittest.TestCase):
	def test_lift_and_scalar_protocols(self):
		lifted = _lift(7)
		signal = Wire(5)

		self.assertIsInstance(lifted, Const)
		self.assertEqual(lifted.eval(), 7)
		self.assertIs(_lift(signal), signal)
		self.assertTrue(bool(signal == 5))
		self.assertEqual(int(signal + 2), 7)
		self.assertEqual(float(signal / 2), 2.5)

	def test_binary_unary_and_comparison_expressions(self):
		a = Const(9)
		b = Const(4)

		self.assertEqual((a + b).eval(), 13)
		self.assertEqual((a - b).eval(), 5)
		self.assertEqual((a * b).eval(), 36)
		self.assertEqual((a / b).eval(), 2.25)
		self.assertEqual((a // b).eval(), 2)
		self.assertEqual((a % b).eval(), 1)
		self.assertEqual((a & b).eval(), 0)
		self.assertEqual((a | b).eval(), 13)
		self.assertEqual((a ^ b).eval(), 13)
		self.assertFalse((a < b).eval())
		self.assertFalse((a <= b).eval())
		self.assertTrue((a > b).eval())
		self.assertTrue((a >= b).eval())
		self.assertFalse((a == b).eval())
		self.assertTrue((a != b).eval())
		self.assertEqual((-b).eval(), -4)
		self.assertEqual((~Const(0b1010)).eval(), ~0b1010)

	def test_mux_and_invalid_operator_paths(self):
		self.assertEqual(Mux(Const(True), 11, 22).eval(), 11)
		self.assertEqual(Mux(Const(False), 11, 22).eval(), 22)
		self.assertIn("Const(3)", repr(Const(3)))
		self.assertIn("UnaryOp(neg", repr(-Const(1)))
		self.assertIn("Op(+", repr(Const(1) + 2))
		self.assertIn("Mux(", repr(Mux(True, 1, 0)))

		with self.assertRaises(ValueError):
			UnaryOp("bad", Const(1)).eval()

		with self.assertRaises(ValueError):
			Op("bad", Const(1), Const(2)).eval()


class SignalAndVectorTests(unittest.TestCase):
	def test_signal_constructors_reset_and_repr(self):
		in_sig = In([1, 2])
		out_sig = Out(0)
		wire = Wire({"nested": [3]})
		reg = Reg(1)

		self.assertEqual(in_sig.kind, "in")
		self.assertEqual(out_sig.kind, "out")
		self.assertEqual(wire.kind, "wire")
		self.assertEqual(reg.kind, "reg")

		wire.value["nested"].append(4)
		wire.reset_value()
		self.assertEqual(wire.value, {"nested": [3]})

		wire.name = "top.some_wire"
		self.assertEqual(repr(wire), "<wire top.some_wire={'nested': [3]}>")

	def test_signal_driver_rules_and_driver_clearing(self):
		wire = Wire(0)
		reg = Reg(0)

		wire @= 9
		self.assertIsInstance(wire.comb_src, Const)
		self.assertEqual(wire.comb_src.eval(), 9)

		reg <<= wire + 1
		self.assertEqual(reg.next_src.eval(), 1)

		wire.clear_drivers()
		reg.clear_drivers()
		self.assertIsNone(wire.comb_src)
		self.assertIsNone(reg.next_src)

		with self.assertRaises(TypeError):
			reg @= 1

		with self.assertRaises(TypeError):
			wire <<= 1

		wire @= 1
		with self.assertRaises(ValueError):
			wire @= 2

		reg <<= 1
		with self.assertRaises(ValueError):
			reg <<= 2

	def test_vec_builds_deeply_cloned_shapes(self):
		vec = Vec((2, 2), Wire([0]))

		self.assertEqual(len(vec), 2)
		self.assertEqual(len(vec[0]), 2)
		self.assertIsInstance(vec[0][0], Signal)
		self.assertIsNot(vec[0][0], vec[0][1])
		self.assertIsNot(vec[0][0], vec[1][0])

		vec[0][0].value.append(1)
		self.assertEqual(vec[0][0].value, [0, 1])
		self.assertEqual(vec[0][1].value, [0])
		self.assertEqual(Vec((), 5), 5)

		with self.assertRaises(TypeError):
			Vec("bad", Wire(0))

	def test_reg_next_state_helpers_support_inline_imperative_style(self):
		top = InlineBranchStage()
		sim = Sim(top)

		sim.step()
		self.assertEqual(sim.peek(top.pc), 1)
		self.assertEqual(sim.peek(top.decode_pc), 1)
		self.assertEqual(sim.peek(top.out), 1)

		sim.poke(top.redirect, True)
		sim.poke(top.target, 7)
		sim.step()
		self.assertEqual(sim.peek(top.pc), 7)
		self.assertEqual(sim.peek(top.decode_pc), 7)
		self.assertEqual(sim.peek(top.out), 7)

		with self.assertRaises(ValueError):
			top.pc.set_next(8)

		with self.assertRaises(TypeError):
			top.out.set_next(0)

	def test_mem_reads_writes_and_bundle_hierarchy(self):
		top = BundleMemoryStage()
		sim = Sim(top)

		sim.poke(top.req.addr, 1)
		sim.poke(top.req.data, 23)
		sim.poke(top.req.write, True)
		sim.step()
		self.assertEqual(sim.peek(top.resp.data), 23)
		self.assertEqual(sim.peek(top.resp.mirror), 23)

		sim.poke(top.req.write, False)
		sim.poke(top.req.addr, 1)
		sim.step()
		self.assertEqual(sim.peek(top.resp.data), 23)

		mods, sigs = _collect(top)
		self.assertEqual(mods, [("top", top)])
		self.assertIn("top.req.addr", [name for name, _ in sigs])
		self.assertIn("top.resp.data", [name for name, _ in sigs])
		self.assertIn("top.mem.cells[1]", [name for name, _ in sigs])

		with self.assertRaises(IndexError):
			top.mem.read(9)

	def test_module_assert_checks_stable_cycle_conditions(self):
		top = GuardedCounter()
		sim = Sim(top)

		sim.poke(top.enable, True)
		sim.poke(top.limit, 2)
		sim.step(2)
		self.assertEqual(sim.peek(top.count), 2)

		with self.assertRaisesRegex(AssertionError, "count overflow"):
			sim.step()


class TraversalAndSimulatorTests(unittest.TestCase):
	def test_collect_finds_hierarchical_modules_and_signal_names(self):
		top = HierarchicalSystem()
		mods, sigs = _collect(top)

		self.assertEqual(repr(top), "<HierarchicalSystem>")
		self.assertIn("top", [name for name, _ in mods])
		self.assertIn("top.children[0]", [name for name, _ in mods])
		self.assertIn("top.children[1]", [name for name, _ in mods])
		self.assertIn("top.bias", [name for name, _ in sigs])
		self.assertIn("top.children[0].left", [name for name, _ in sigs])
		self.assertIn("top.pipes[1]", [name for name, _ in sigs])

	def test_sim_poke_peek_and_free_functions(self):
		top = CombChain()
		sim = Sim(top)

		sim.poke(top.src, 5)
		self.assertEqual(sim.peek(top.src), 5)

		poke(top.src, 8)
		self.assertEqual(peek(top.src), 8)

		with self.assertRaises(TypeError):
			sim.poke(123, 1)

		with self.assertRaises(TypeError):
			sim.peek(123)

	def test_settle_updates_combinational_chain_and_records_changes(self):
		top = CombChain()
		sim = Sim(top)
		sim.poke(top.src, 4)

		sim.settle()

		self.assertEqual(sim.peek(top.mid), 6)
		self.assertEqual(sim.peek(top.out), 18)
		self.assertEqual([(sig.name, old, new) for sig, old, new in sim.changed()], [
			("top.out", 0, 18),
		])

	def test_step_run_and_until_keep_outputs_cycle_consistent(self):
		top = RegisterStage()
		sim = Sim(top)
		sim.poke(top.enable, True)
		sim.poke(top.inc, 3)

		sim.step()
		self.assertEqual(sim.cycle, 1)
		self.assertEqual(sim.peek(top.state), 3)
		self.assertEqual(sim.peek(top.out), 3)
		self.assertEqual([(sig.name, old, new) for sig, old, new in sim.changed()], [
			("top.state", 0, 3),
			("top.out", 0, 3),
		])

		returned = sim.run(2)
		self.assertIs(returned, sim)
		self.assertEqual(sim.cycle, 3)
		self.assertEqual(sim.peek(top.state), 9)
		self.assertEqual(sim.peek(top.out), 9)

		reached = sim.until(lambda: sim.peek(top.out) >= 15, max_cycles=3)
		self.assertTrue(reached)
		self.assertEqual(sim.peek(top.out), 15)

	def test_state_dump_watch_and_trace_output(self):
		top = RegisterStage()
		sim = Sim(top)
		sim.poke(top.enable, True)
		sim.poke(top.inc, 2)

		self.assertEqual(sim.state(include_inputs=False), [
			("top.state", 0),
			("top.out", 0),
		])

		sim.watch(top.out)
		stream = io.StringIO()
		with redirect_stdout(stream):
			sim.step(trace=True)
			sim.dump(include_inputs=False)
		output = stream.getvalue()

		self.assertIn("[cycle 0 settle 0]", output)
		self.assertIn("top.out: 0 -> 2", output)
		self.assertIn("[cycle 0 commit]", output)
		self.assertNotIn("top.state: 0 -> 2", output)
		self.assertIn("[cycle 1]", output)
		self.assertIn("top.out = 2", output)

		sim.unwatch()
		self.assertEqual(sim.watchlist, [])

	def test_hierarchical_vectors_and_registers_integrate_across_cycles(self):
		top = HierarchicalSystem()
		sim = Sim(top)
		sim.poke(top.bias, 10)

		sim.step()
		self.assertEqual(sim.peek(top.pipes[0]), 1)
		self.assertEqual(sim.peek(top.pipes[1]), 11)
		self.assertEqual(sim.peek(top.total), 11)

		sim.step()
		self.assertEqual(sim.peek(top.pipes[0]), 2)
		self.assertEqual(sim.peek(top.pipes[1]), 12)
		self.assertEqual(sim.peek(top.total), 12)
		self.assertEqual(sim.state(include_inputs=False), [
			("top.children[0].out", 12),
			("top.children[1].out", 13),
			("top.pipes[0]", 2),
			("top.pipes[1]", 12),
			("top.total", 12),
		])

	def test_comb_loop_raises_after_max_settle(self):
		sim = Sim(Oscillator(), max_settle=4)

		with self.assertRaises(RuntimeError):
			sim.settle()


class IntegrationHardwareTests(unittest.TestCase):
	def test_pipelined_processor_stages_and_branch_flush(self):
		program = [
			("LOADI", 0, 2),
			("LOADI", 1, 0),
			("BZ", 1, 4),
			("LOADI", 0, 99),
			("ADDI", 0, 5),
			("STORE", 0, 0),
			("HALT",),
		]
		top = PipelinedMiniProcessor(program)
		sim = Sim(top)

		stage_trace = []
		for _ in range(5):
			sim.step()
			stage_trace.append((
				sim.peek(top.fetch_pc_out),
				sim.peek(top.decode_op_out),
				sim.peek(top.acc_out),
			))

		self.assertEqual(stage_trace, [
			(0, "NOP", 0),
			(1, "LOADI", 0),
			(2, "LOADI", 2),
			(3, "BZ", 2),
			(4, "NOP", 2),
		])
		self.assertEqual(sim.peek(top.decode_pc_out), -1)
		self.assertEqual(sim.peek(top.regs[0]), 2)

		reached = sim.until(lambda: sim.peek(top.halted_out), max_cycles=10)
		self.assertTrue(reached)
		self.assertEqual(sim.peek(top.regs[0]), 7)
		self.assertEqual(sim.peek(top.regs[1]), 0)
		self.assertEqual([sim.peek(word) for word in top.data], [7, 0, 0, 0])
		self.assertEqual(sim.peek(top.retired), 6)
		self.assertTrue(sim.peek(top.halted_out))

	def test_mini_processor_executes_looping_program_and_sticks_after_halt(self):
		program = [
			("LOADI", 0, 0),
			("LOADI", 1, 5),
			("ADD", 0, 1),
			("SUBI", 1, 1),
			("JNZ", 1, 2),
			("STORE", 0, 0),
			("LOAD", 3, 0),
			("ADDI", 3, 7),
			("STORE", 3, 1),
			("HALT",),
		]
		top = MiniProcessor(program)
		sim = Sim(top)

		pc_trace = []
		acc_trace = []
		for _ in range(8):
			sim.step()
			pc_trace.append(sim.peek(top.pc))
			acc_trace.append(sim.peek(top.acc_out))

		self.assertEqual(pc_trace, [1, 2, 3, 4, 2, 3, 4, 2])
		self.assertEqual(acc_trace, [0, 0, 5, 5, 5, 9, 9, 9])
		self.assertFalse(sim.peek(top.halted_out))

		reached = sim.until(lambda: sim.peek(top.halted_out), max_cycles=20)
		self.assertTrue(reached)
		self.assertEqual(sim.peek(top.acc_out), 15)
		self.assertEqual(sim.peek(top.regs[0]), 15)
		self.assertEqual(sim.peek(top.regs[1]), 0)
		self.assertEqual(sim.peek(top.regs[3]), 22)
		self.assertEqual([sim.peek(word) for word in top.data], [15, 22, 0, 0])
		self.assertEqual(sim.peek(top.pc_out), 10)
		self.assertEqual(sim.peek(top.retired), 22)

		state_before = {
			"pc": sim.peek(top.pc),
			"halted": sim.peek(top.halted),
			"retired": sim.peek(top.retired),
			"regs": [sim.peek(reg) for reg in top.regs],
			"data": [sim.peek(word) for word in top.data],
		}
		sim.step()
		state_after = {
			"pc": sim.peek(top.pc),
			"halted": sim.peek(top.halted),
			"retired": sim.peek(top.retired),
			"regs": [sim.peek(reg) for reg in top.regs],
			"data": [sim.peek(word) for word in top.data],
		}

		self.assertEqual(state_after, state_before)

	def test_iterative_multiplier_completes_and_ignores_restart_while_busy(self):
		top = ShiftAddMultiplier(width=6)
		sim = Sim(top)

		sim.poke(top.start, True)
		sim.poke(top.multiplicand, 13)
		sim.poke(top.multiplier, 11)
		sim.step()

		self.assertTrue(sim.peek(top.busy))
		self.assertFalse(sim.peek(top.done))
		self.assertEqual(sim.peek(top.result), 0)

		sim.poke(top.start, False)
		partial_products = []
		for _ in range(3):
			sim.step()
			partial_products.append(sim.peek(top.result))

		self.assertEqual(partial_products, [13, 39, 39])

		sim.poke(top.start, True)
		sim.poke(top.multiplicand, 99)
		sim.poke(top.multiplier, 99)
		sim.step()
		self.assertEqual(sim.peek(top.result), 143)
		self.assertTrue(sim.peek(top.busy))

		sim.poke(top.start, False)
		sim.run(2)
		self.assertEqual(sim.peek(top.result), 143)
		self.assertFalse(sim.peek(top.busy))
		self.assertTrue(sim.peek(top.done))

	def test_overlapping_sequence_detector_counts_multiple_matches(self):
		top = SequenceDetector1011()
		sim = Sim(top)

		observed_matches = []
		for bit in [1, 0, 1, 1, 0, 1, 1]:
			sim.poke(top.bit_in, bit)
			sim.step()
			observed_matches.append(bool(sim.peek(top.match)))

		self.assertEqual(observed_matches, [False, False, False, True, False, False, True])
		self.assertEqual(sim.peek(top.match_count), 2)
		self.assertEqual(sim.peek(top.state), 1)

	def test_four_tap_filter_tracks_sample_history_and_holds_when_disabled(self):
		top = FourTapFilter()
		sim = Sim(top)

		outputs = []
		for sample in [3, 1, 4, 1, 5]:
			sim.poke(top.sample, sample)
			sim.step()
			outputs.append(sim.peek(top.filtered))

		self.assertEqual(outputs, [3, 7, 15, 24, 23])
		self.assertEqual([sim.peek(stage) for stage in top.delay], [5, 1, 4, 1])

		sim.poke(top.enable, False)
		sim.poke(top.sample, 9)
		sim.step()
		self.assertEqual(sim.peek(top.filtered), 23)
		self.assertEqual([sim.peek(stage) for stage in top.delay], [5, 1, 4, 1])


if __name__ == "__main__":
	unittest.main(verbosity=2)
