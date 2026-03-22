from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pyrtlite import *

class PE(Module):
    def build(self):
        self.a_in  = In(0.0)
        self.b_in  = In(0.0)
        self.rst   = In(False)

        self.a_out = Reg(0.0)
        self.b_out = Reg(0.0)
        self.acc   = Reg(0.0)

    def logic(self):
        self.a_out <<= self.a_in
        self.b_out <<= self.b_in

        if self.rst: 
            self.acc <<= 0
        else: 
            self.acc <<= self.acc + (self.a_in * self.b_in)

class Systolic(Module):
    def build(self, n): 
        self.n     = n
        self.rst   = In(False)
        self.a_in  = Vec(n, In(0.0))
        self.b_in  = Vec(n, In(0.0))
        self.c_out = Vec((n, n), Out(0.0))
        self.pes   = Vec((n, n), PE())

    def logic(self): 
        for i in range(self.n):
            for j in range(self.n): 
                pe = self.pes[i][j]

                if j == 0: 
                    pe.a_in @= self.a_in[i]
                else:
                    pe.a_in @= self.pes[i][j - 1].a_out
                if i == 0:
                    pe.b_in @= self.b_in[j]
                else: 
                    pe.b_in @= self.pes[i - 1][j].b_out
                
                pe.rst @= self.rst
                self.c_out[i][j] @= pe.acc

class DS():
    Idle = 0
    Busy = 1
    Done = 2

class Driver(Module): 
    def build(self, n): 
        self.n       = n
        self.cycles  = Reg(0)
        self.start   = In(False)
        self.state   = Reg(DS.Idle)
        self.done    = Out(False)
        self.c_out   = Vec((n, n), Out(0))
        self.mem_a   = Mem(n * n)
        self.mem_b   = Mem(n * n)
        self.array   = Systolic(n)

    def logic(self): 
        match self.state: 
            case DS.Idle: 
                if self.start: 
                    self.array.rst @= True
                    self.cycles    <<= 0
                    self.state     <<= DS.Busy
                    
            case DS.Busy: 
                self.array.rst @= False
                self.cycles    <<= self.cycles + 1

                if self.cycles >= 2 * self.n + 1: 
                    self.done  @= True
                    self.state <<= DS.Done
                else: 
                    self.done  @= False

                for i in range(self.n): 
                    if self.cycles >= i and self.cycles < i + self.n: 
                        self.array.a_in[i] @= self.mem_a[i * self.n + (self.cycles - i)]
                        self.array.b_in[i] @= self.mem_b[(self.cycles - i) * self.n + i]
                    else: 
                        self.array.a_in[i] @= 0.0
                        self.array.b_in[i] @= 0.0

                for i in range(self.n): 
                    for j in range(self.n): 
                        self.c_out[i][j] @= self.array.pes[i][j].acc

            case DS.Done:
                self.done  @=  False
                self.state <<= DS.Idle

def load(driver, n, a, b): 
    for i in range(n): 
        for j in range(n):
            driver.mem_a[(i * n) + j] = float(a[i][j])
            driver.mem_b[(i * n) + j] = float(b[i][j])

def run(n, a, b, trace = False): 
    driver = Driver(n)
    sim = Sim(driver)

    load(driver, n, a, b)

    sim.poke(driver.start, True)
    sim.step()
    sim.poke(driver.start, False)
    sim.until(driver.done, trace = trace)
    c = driver.c_out.to_list()

    return c

def ref(n, a, b): 
    c = [[0 for _ in range(n)] for _ in range(n)]

    for i in range(n):
        for j in range(n):
            for k in range(n):
                c[i][j] += float(a[i][k] * b[k][j])
    return c


if __name__ == "__main__": 
    n = 3

    a = [
        [1, 0, 0],
        [1, 1, 0], 
        [1, 1, 1]
    ]

    b = [
        [1, 2, 1], 
        [1, 3, 1], 
        [1, 1, 3]
    ]

    c_sys = run(n, a, b, trace = True)
    c_ref = ref(n, a, b)

    print("matmul completed")
    print("\nsystolic:")
    for i in range(n):
        print(f"{c_sys[i]}")
    print("\nreference:")
    for i in range(n):
        print(f"{c_ref[i]}")