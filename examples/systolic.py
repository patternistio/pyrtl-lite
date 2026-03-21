from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pyrtlite import *

class PE(Module):
    def build(self):
        self.a_in  = In(0.0)
        self.b_in  = In(0.0)
        self.clr   = In(False)

        self.a_out = Reg(0.0)
        self.b_out = Reg(0.0)
        self.acc   = Reg(0.0)

    def logic(self):
        self.a_out <<= self.a_in
        self.b_out <<= self.b_in

        if self.clear: 
            self.acc <<= 0
        else: 
            self.acc <<= self.acc + (self.a_in * self.a_in)

# will finish this tmr