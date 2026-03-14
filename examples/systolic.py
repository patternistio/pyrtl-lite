from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pyrtlite import In, Mem, Module, Out, Reg, Sim, Vec


class PE(Module):

    def build(self):
        self.a_in = In(0)
        self.b_in = In(0)
        self.clear = In(0)

        self.a_out = Reg(0)
        self.b_out = Reg(0)
        self.acc = Reg(0)

    def logic(self):
        a_now = int(self.a_in.nxt)
        b_now = int(self.b_in.nxt)

        self.a_out <<= a_now
        self.b_out <<= b_now

        if int(self.clear.nxt):
            self.acc <<= 0
        else:
            self.acc <<= int(self.acc) + (a_now * b_now)


class Systolic(Module):

    def build(self, n):
        if n <= 0:
            raise ValueError("n must be >= 1")

        self.n = n
        self.clear = In(0)
        self.in_a = Vec(n, In(0))
        self.in_b = Vec(n, In(0))
        self.out_c = Vec((n, n), Out(0))
        self.pes = Vec((n, n), PE())

    def logic(self):
        for i in range(self.n):
            for j in range(self.n):
                pe = self.pes[i][j]

                if j == 0:
                    pe.a_in @= self.in_a[i]
                else:
                    pe.a_in @= self.pes[i][j - 1].a_out

                if i == 0:
                    pe.b_in @= self.in_b[j]
                else:
                    pe.b_in @= self.pes[i - 1][j].b_out

                pe.clear @= self.clear
                self.out_c[i][j] @= pe.acc


class MMU(Module):

    def build(self, n):
        if n <= 0:
            raise ValueError("n must be >= 1")

        self.n = n
        self.total_cycles = 3 * n

        self.start = In(0)
        self.done = Out(0)
        self.out_c = Vec((n, n), Out(0))

        self.mem_a = Mem(n * n, init=0)
        self.mem_b = Mem(n * n, init=0)

        self.array = Systolic(n)

        self.running = Reg(0)
        self.tick = Reg(0)
        self.done_reg = Reg(0)

    def logic(self):
        running = int(self.running)
        tick = int(self.tick)

        self.running <<= running
        self.tick <<= tick
        self.done_reg <<= int(self.done_reg)

        if int(self.start):
            self.running <<= 1
            self.tick <<= 0
            self.done_reg <<= 0
        elif running:
            next_tick = tick + 1
            self.tick <<= next_tick
            if next_tick >= self.total_cycles:
                self.running <<= 0
                self.done_reg <<= 1

        self.array.clear @= self.start

        for i in range(self.n):
            a_val = 0
            if running:
                k = tick - 1 - i
                if 0 <= k < self.n:
                    a_val = int(self.mem_a[(i * self.n) + k])
            self.array.in_a[i] @= a_val

        for j in range(self.n):
            b_val = 0
            if running:
                k = tick - 1 - j
                if 0 <= k < self.n:
                    b_val = int(self.mem_b[(k * self.n) + j])
            self.array.in_b[j] @= b_val

        for i in range(self.n):
            for j in range(self.n):
                self.out_c[i][j] @= self.array.out_c[i][j]

        self.done @= self.done_reg


def _validate_square(mat, n, name):
    if len(mat) != n:
        raise ValueError(f"{name} must have {n} rows")
    for r, row in enumerate(mat):
        if len(row) != n:
            raise ValueError(f"{name}[{r}] must have {n} columns")


def load_matrix(mem, matrix):
    n = len(matrix)
    for i in range(n):
        for j in range(n):
            mem.cells[(i * n) + j].value = int(matrix[i][j])


def read_matrix(sim, out_vec):
    n = len(out_vec)
    return [[sim.peek(out_vec[i][j]) for j in range(n)] for i in range(n)]


def run_mmu(a, b, trace=False):
    n = len(a)
    _validate_square(a, n, "A")
    _validate_square(b, n, "B")

    top = MMU(n)
    load_matrix(top.mem_a, a)
    load_matrix(top.mem_b, b)

    sim = Sim(top)

    sim.poke(top.start, 1)
    sim.step(trace=trace)
    sim.poke(top.start, 0)

    for _ in range(top.total_cycles + 2):
        sim.step(trace=trace)
        if sim.peek(top.done):
            break

    return read_matrix(sim, top.out_c)


def matmul_ref(a, b):
    n = len(a)
    out = [[0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            total = 0
            for k in range(n):
                total += int(a[i][k]) * int(b[k][j])
            out[i][j] = total
    return out


if __name__ == "__main__":
    a2 = [
        [1, 2],
        [3, 4],
    ]
    b2 = [
        [5, 6],
        [7, 8],
    ]

    c2 = run_mmu(a2, b2, trace=False)

    print("2x2 result:")
    for row in c2:
        print(row)
    print("2x2 expected:")
    for row in matmul_ref(a2, b2):
        print(row)

    a3 = [
        [2, 1, 0],
        [1, 3, 2],
        [4, 0, 1],
    ]
    b3 = [
        [1, 2, 3],
        [0, 1, 4],
        [5, 6, 0],
    ]

    c3 = run_mmu(a3, b3, trace=False)

    print("\n3x3 result:")
    for row in c3:
        print(row)
    print("3x3 expected:")
    for row in matmul_ref(a3, b3):
        print(row)
