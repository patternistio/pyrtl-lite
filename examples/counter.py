from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pyrtlite import *


class Counter(Module):
	
	def build(self, limit=16):
		self.en = In(1)
		self.q = Out(0)
		self.count = Reg(0)
		self.limit = limit

	def logic(self):
		next_count = (self.count + 1) % self.limit
		self.count <<= Mux(self.en, next_count, self.count)
		self.q @= self.count


if __name__ == "__main__":
	top = Counter(limit=8)
	sim = Sim(top)

	sim.poke(top.en, 1)
	print("cycle q")
	for cycle in range(10):
		sim.step()
		print(cycle, sim.peek(top.q))