from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pyrtlite import *


class Counter(Module):

	def build(self):
		self.start = In(0)
		self.rst = In(0)
		self.period = In(8)

		self.count = Reg(0)
		self.q = Out(0)
		self.wrap = Out(0)

	def logic(self):
		period = int(self.period)
		count = int(self.count)

		self.wrap @= 0
		self.count <<= count

		if int(self.rst):
			self.count <<= 0
		elif int(self.start):
			if period <= 1:
				self.count <<= 0
				self.wrap @= 1
			elif count >= (period - 1):
				self.count <<= 0
				self.wrap @= 1
			else:
				self.count <<= count + 1

		self.q @= self.count


if __name__ == "__main__":
	top = Counter()
	sim = Sim(top)

	sim.poke(top.rst, 1)
	sim.poke(top.start, 0)
	sim.poke(top.period, 5)
	sim.step()

	sim.poke(top.rst, 0)
	sim.poke(top.start, 1)

	print("cycle count wrap")
	for cycle in range(10):
		sim.step()
		print(cycle, sim.peek(top.q), sim.peek(top.wrap))