# pyrtl(-lite).py
# a minimal hardware-ish simulator

import copy

# ------------------------------------------------------------------------
# expressions
# ------------------------------------------------------------------------

class Expr: 
    def eval(self):
        raise NotImplementedError
    
    def __bool__(self):
        return bool(self.eval())
    
    def __int__(self):
        return int(self.eval())
    
    def __float__(self):
        return float(self.eval())
    
    def _bin(self, op, other): 
        return Op(op, self, _lift(other))
    
    def _rbin(self, op, other): 
        return Op(op, _lift(other), self)
    
    def __add__(self, other):  return self._bin("+", other)
    def __radd__(self, other): return self._rbin("+", other)
    def __sub__(self, other):  return self._bin("-", other)
    def __rsub__(self, other): return self._rbin("-", other)
    def __mul__(self, other):  return self._bin("*", other)
    def __rmul__(self, other): return self._rbin("*", other)
    
    def __truediv__(self, other):   return self._bin("/", other)
    def __rtruediv__(self, other):  return self._rbin("/", other)
    def __floordiv__(self, other):  return self._bin("//", other)
    def __rfloordiv__(self, other): return self._rbin("//", other)
    
    def __mod__(self, other):  return self._bin("%", other)
    def __rmod__(self, other): return self._rbin("%", other)

    def __and__(self, other):  return self._bin("&", other)
    def __rand__(self, other): return self._rbin("&", other)
    def __or__(self, other):   return self._bin("|", other)
    def __ror__(self, other):  return self._rbin("|", other)
    def __xor__(self, other):  return self._bin("^", other)
    def __rxor__(self, other): return self._rbin("^", other)

    def __lt__(self, other): return self._bin("<", other)
    def __le__(self, other): return self._bin("<=", other)
    def __gt__(self, other): return self._bin(">", other)
    def __ge__(self, other): return self._bin(">=", other)
    def __eq__(self, other): return self._bin("==", other)
    def __ne__(self, other): return self._bin("!=", other)

    def __neg__(self):    return UnaryOp("neg", self)
    def __invert__(self): return UnaryOp("invert", self)

def _lift(x):
    if isinstance(x, Expr):
        return x
    return Const(x)

class Const(Expr): 
    def __init__(self, value):
        self.value = value

    def eval(self): 
        return self.value
    
    def __str__(self):
        return f"Const({self.value})"
    
class UnaryOp(Expr): 
    def __init__(self, op, x):
        self.op = op
        self.x = _lift(x)

    def eval(self):
        x = self.x.eval()
        if self.op == "neg":    return -x
        if self.op == "invert": return ~x
        raise ValueError(f"Unknown unary op {self.op}")
    
    def __str__(self): 
        return f"UnaryOp({self.op}, {self.x})"
    
class Op(Expr): 
    def __init__(self, op, a, b):
        self.op = op
        self.a = _lift(a)
        self.b = _lift(b)

    def eval(self): 
        a = self.a.eval()
        b = self.b.eval()
        if self.op == "+":  return a + b
        if self.op == "-":  return a - b
        if self.op == "*":  return a * b
        if self.op == "/":  return a / b
        if self.op == "//": return a // b
        if self.op == "%":  return a % b
        if self.op == "&":  return a & b
        if self.op == "|":  return a | b
        if self.op == "^":  return a ^ b
        if self.op == "<":  return a < b
        if self.op == "<=": return a <= b
        if self.op == ">":  return a > b
        if self.op == ">=": return a >= b
        if self.op == "==": return a == b
        if self.op == "!=": return a != b
        raise ValueError(f"Unknown op {self.op}")
    
    def __str__(self):
        return f"Op({self.op}, {self.a}, {self.b})"
    
class _Mux(Expr): 
    def __init__(self, cond, a, b): 
        self.cond = cond
        self.a = a
        self.b = b

    def eval(self):
        return self.a.eval() if self.cond.eval() else self.b.eval()

    def __str__(self):
        return f"Mux({self.cond}, {self.a}, {self.b})"

def Mux(cond, a, b):
    return _Mux(_lift(cond), _lift(a), _lift(b))

class _ScheduledValue(Expr):
    def __init__(self, signal):
        self.signal = signal 

    def eval(self):
        return self.signal.eval_scheduled()
    
    def __str__(self):
        return f"ScheduledValue({self.signal})"
    
# ------------------------------------------------------------------------
# signals
# ------------------------------------------------------------------------

class Signal(Expr): 
    def __init__(self, init = 0, kind = "wire"):
        self.init  = init
        self.kind  = kind
        self.value = copy.deepcopy(init)
        self.name  = None
        self.comb_src = None
        self.next_src = None

    def eval(self):
        return self.value
    
    def eval_scheduled(self):
        if self.kind == "reg" and self.next_src is not None:
            return self.next_src.eval()
        if self.kind != "reg" and self.comb_src is not None: 
            return self.comb_src.eval()
        return self.value
    
    @property
    def nxt(self):
        return _ScheduledValue(self)
    
    def reset_value(self):
        self.value = copy.deepcopy(self.init)

    def clear_drivers(self):
        self.comb_src = None
        self.next_src = None

    def __imatmul__(self, rhs):
        if self.kind == "reg":
            raise TypeError(f"Cannot combinationally drive register {self.name}, use <<=")
        # Last assignment in a single logic pass wins, which allows
        # default assignments followed by conditional overrides.
        self.comb_src = _lift(rhs)
        return self
    
    def set_next(self, rhs, overwrite = False):
        if self.kind != "reg": 
            raise TypeError(f"Can only sequentially assign register, not {self.kind} {self.name}")
        # Last assignment in a single logic pass wins for registers too.
        # Keep explicit overwrite flag for API compatibility.
        if self.next_src is not None and not overwrite:
            pass
        self.next_src = _lift(rhs)
        return self
    
    def __ilshift__(self, rhs): 
        return self.set_next(rhs)
    
    def __str__(self): 
        n = self.name if self.name is not None else "?"
        return f"{self.kind}({n} = {self.value})"
    
def In(init = 0):   return Signal(init, "in")
def Out(init = 0):  return Signal(init, "out")
def Wire(init = 0): return Signal(init, "wire")
def Reg(init = 0): return Signal(init, "reg")

# ------------------------------------------------------------------------
# vectors
# ------------------------------------------------------------------------

def _clone(x):
    return copy.deepcopy(x)

def Vec(shape, proto):
    if isinstance(shape, int):
        return [_clone(proto) for _ in range(shape)]
    if isinstance(shape, tuple):
        if len(shape) == 0:
            return _clone(proto)
        if len(shape) == 1: 
            return [_clone(proto) for _ in range(shape[0])]
        n = shape[0]
        rest = shape[1:]
        return [Vec(rest, proto) for _ in range(n)]
    raise TypeError("Vec shape must be int or tuple")

class Mem(): 
    def __init__(self, depth, init = 0):
        self.depth = depth
        self.cells = Vec(depth, Reg(init))

    def _index(self, addr): 
        index = int(addr)
        if not 0 <= index < self.depth:
            raise IndexError(f"Memory address {index} out of range for depth {self.depth}")
        return index
    
    def read(self, addr): 
        return self.cells[self._index(addr)]
    
    def write(self, addr, value):
        self.cells[self._index(addr)] <<= value

    def __getitem__(self, addr): 
        return self.read(addr)

    def __setitem__(self, addr, value):
        # Needed for Python augmented assignment support on indexed memory.
        # Example: mem[i] <<= x triggers __getitem__, then __setitem__.
        idx = self._index(addr)
        cell = self.cells[idx]
        if isinstance(value, Signal) and value is cell:
            return
        cell <<= value
    
    def __len__(self):
        return self.depth 
    
    def __str__(self):
        return f"Mem()"

# ------------------------------------------------------------------------
# module system
# ------------------------------------------------------------------------

class Module: 
    def __init__(self, *args, **kwargs):
        self.build(*args, **kwargs)

    def build(self, *args, **kwargs):
        pass

    def logic(self):
        pass

    def Assert(self, cond, message = "Assertion failed"):
        if not hasattr(self, "_assertions"):
            self._assertions = []
        self._assertions.append((_lift(cond), message))

    def __str__(self):
        return f"Module({self.__class__.__name__})"
    
def _walk_obj(x, path, mods, sigs): 
    if isinstance(x, Module):
        mods.append((path, x))
        for k, v in x.__dict__.items():
            _walk_obj(v, f"{path}.{k}" if path else k, mods, sigs)
    elif isinstance(x, Signal): 
        x.name = path
        sigs.append((path, x))
    elif isinstance(x, Mem):
        for k, v in x.__dict__.items():
            _walk_obj(v, f"{path}.{k}" if path else k, mods, sigs)
    elif isinstance(x, (list, tuple)): 
        for i, v in enumerate(x): 
            _walk_obj(v, f"{path}[{i}]", mods, sigs)

def _collect(top):
    mods, sigs = [], []
    _walk_obj(top, "top", mods, sigs)
    return mods, sigs

# ------------------------------------------------------------------------
# simulator
# ------------------------------------------------------------------------

class Sim:
    def __init__(self, top, max_settle = 100):
        self.top = top
        self.max_settle = max_settle
        self.cycle = 0 
        self.mods, self.sigs_named = _collect(top)
        self.sigs = [s for _, s in self.sigs_named]
        self.regs = [s for s in self.sigs if s.kind == "reg"]
        self.comb = [s for s in self.sigs if s.kind != "reg"]
        self.watchlist = []
        self.last_changes = []

    # --- outward ---

    def poke(self, sig, value): 
        if not isinstance(sig, Signal):
            raise TypeError("Poke expects a signal")
        sig.value = value

    def peek(self, sig):
        if not isinstance(sig, Signal):
            raise TypeError("Peek expects a signal")
        return sig.value
    
    def watch(self, *signals):
        self.watchlist.extend(signals)
        return self
    
    def unwatch(self):
        self.watchlist = []
        return self
    
    def changed(self):
        return list(self.last_changes)
    
    def state(self, include_inputs = True): 
        out = []
        for _, s in self.sigs_named: 
            if not include_inputs and s.kind == "in":
                continue
            out.append((s.name, s.value))
        return out
    
    def dump(self, include_inputs = True):
        print(f"[cycle {self.cycle}]")
        for name, value in self.state(include_inputs = include_inputs):
            print(f"  {name} = {value}")
    
    def settle(self, trace = False):
        self._prepare_cycle()
        self._run_logic()
        self._settle_comb(trace = trace)
        self._check_assertions()

    def step(self, n = 1, trace = False):
        for _ in range(n):
            self._prepare_cycle()
            self._run_logic()
            self._settle_comb(trace = trace)
            self._check_assertions()
            self._eval_next()
            self._commit(trace = trace)
            reg_changes = list(self.last_changes)
            self._prepare_cycle()
            self._run_logic()
            self._settle_comb(trace = trace)
            self.last_changes = reg_changes + list(self.last_changes)
            self.cycle += 1
        return self
    
    def run(self, n, trace = False):
        return self.step(n, trace = trace)
    
    def until(self, pred, max_cycles = 1000, trace = False):
        for _ in range(max_cycles):
            if pred():
                return True
            self.step(trace = trace)
        return bool(pred())
    
    # --- inward ---

    def _prepare_cycle(self):
        self.last_changes = []
        for _, m in self.mods:
            m._assertions = []
        for s in self.sigs:
            s.clear_drivers()

    def _check_assertions(self):
        for path, module in self.mods:
            for cond, message in getattr(module, "_assertions", []):
                if not cond.eval():
                    raise AssertionError(f"{path}: {message}")
    
    def _run_logic(self):
        for _, m in self.mods:
            m.logic()

    def _settle_comb(self, trace = False):
        last_wave = []
        for it in range(self.max_settle):
            changed = []
            for s in self.comb:
                if s.kind == "in" and s.comb_src is None: 
                    continue
                if s.comb_src is None:
                    continue
                new = s.comb_src.eval()
                if new != s.value: 
                    changed.append((s, s.value, new))
            if not changed:
                self.last_changes = last_wave
                return
            last_wave = changed
            self.last_changes = changed
            for s, _, new in changed:
                s.value = new
            if trace: 
                print(f"[cycle {self.cycle} settle {it}]")
                for s, old, new in changed: 
                    if not self.watchlist or s in self.watchlist:
                        print(f"  {s.name}: {old} -> {new}")
        raise RuntimeError("Combinational logic did not settle, check for a combinational loop")

    def _eval_next(self):
        for r in self.regs:
            if r.next_src is not None:
                r._next_value = r.next_src.eval()
            else:
                r._next_value = r.value

    def _commit(self, trace = False):
        changed = []
        for r in self.regs:
            new = r._next_value
            old = r.value
            if new != old: 
                changed.append((r, old, new))
            r.value = new
        self.last_changes = changed
        if trace and changed:
            print(f"[cycle {self.cycle} commit]")
            for r, old, new in changed: 
                if not self.watchlist or r in self.watchlist: 
                    print(f"  {r.name}: {old} -> {new}")

# ------------------------------------------------------------------------
# extra macros
# ------------------------------------------------------------------------

def poke(sig, value):
    sig.value = value

def peek(sig):
    return sig.value