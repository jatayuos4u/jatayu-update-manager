"""Conservative parser and fingerprint for APT's simulated upgrade plan.

A preview is not an authorization mechanism. Authentication is enforced by Polkit.
The privileged helper re-simulates to reduce preview/commit discrepancies.
"""
import hashlib
from dataclasses import dataclass

class SimulationError(ValueError):
    pass

@dataclass(frozen=True)
class Simulation:
    installs: tuple[str, ...]
    digest: str

def parse_simulation(output: str) -> Simulation:
    if not isinstance(output, str):
        raise SimulationError('Invalid APT simulation output')
    # Bound untrusted command output before constructing a potentially large
    # parsed transaction plan.
    if len(output) > 1_000_000:
        raise SimulationError('APT simulation output exceeds limits.')
    installs, removals, plan = [], [], []
    for line in output.splitlines():
        if line.startswith(('Inst ', 'Remv ', 'Conf ')):
            plan.append(line)
            if line.startswith('Inst '):
                installs.append(line)
            if line.startswith('Remv '):
                removals.append(line)
    if removals:
        raise SimulationError('APT simulation proposed package removals; operation blocked.')
    if not installs:
        raise SimulationError('No package installations/upgrades proposed; operation blocked.')
    if len(plan) > 10_000:
        raise SimulationError('APT simulation output exceeds limits.')
    digest = hashlib.sha256(('\n'.join(plan) + '\n').encode('utf-8')).hexdigest()
    return Simulation(tuple(installs), digest)
