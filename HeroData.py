import numpy as np
from copy import deepcopy

BASE_RESISTANCES = {
        "Smashing": 0,
        "Lethal": 0,
        "Energy": 0,
        "Negative": 0,
        "Psychic": 0,
        "Fire": 0,
        "Cold": 0,
        "Toxic": 0
    }


class Arena:
    ARENA = None
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.time = 0
        self.tic_size = 0.132
        self.hero = None
        self.living_mobs = []
        self.dead_mobs = []
        self.rng = np.random.default_rng()
        Arena.ARENA = self
        self.debuff_active_time_per_mob = {}
        self.mob_lifetimes = {}
        self.verbosity=0
        for t in TimedObject.TIMED_OBJECT_LIST:
            t.reset()
            
        
    def add_hero(self, hero):
        self.hero = hero
        self.hero.arena = self
        
        
    def add_mob(self, mob):
        self.living_mobs.append(mob)
        self.mob_lifetimes[mob.id] = self.tic_size
        self.debuff_active_time_per_mob[mob.id]={}
        
        
    def tic(self):
        self.time += self.tic_size
        for obj in TimedObject.TIMED_OBJECT_LIST:
            obj.time_tic()
        
        
    def start_simulation(self):
        while len(self.living_mobs) > 0:
            self.tic()
            self.hero()
            new_dead_mobs = []
            for idx,mob in enumerate(self.living_mobs):
                if not mob.alive:
                    new_dead_mobs.append(mob.id)
                    self.dead_mobs.append(mob)
                else:
                    self.mob_lifetimes[mob.id] += self.tic_size
                    for name,debuff in mob.debuffs.items():
                        time_add = self.tic_size
                        if debuff.time_completed < 0:
                            time_add = 0
                        if name in self.debuff_active_time_per_mob[mob.id]:
                            self.debuff_active_time_per_mob[mob.id][name] += self.tic_size
                        else:
                            self.debuff_active_time_per_mob[mob.id][name] = self.tic_size
                        
            living_at_start = len(self.living_mobs)
            for mob_id in new_dead_mobs:
                for idx,m in enumerate(self.living_mobs):
                    if m.id == mob_id:
                        for name, correction in m.debuff_time_correction.items():
                            if name in self.debuff_active_time_per_mob[m.id]:
                                self.debuff_active_time_per_mob[m.id][name] += correction
                        del self.living_mobs[idx]
                        break
            if self.verbosity >= 1:
                print(f"At time {self.time:.03f} number of mobs living {len(self.living_mobs)}       ", end='\r')
        TimedObject.clear_unused_timers()


class TimedObject:
    TIMED_OBJECT_LIST = []
    def __init__(self, duration, tic_rate=1):
        self.time_start = None
        self.duration = duration
        self.time_completed = 0
        self.tic_rate = tic_rate
        self.on_cooldown = False
        self.finished = False
        self.TIMED_OBJECT_LIST.append(self)
        self.id = len(self.TIMED_OBJECT_LIST) - 1
        
        
    def reset(self):
        self.time_start = None
        self.time_completed = 0
        self.on_cooldown = False
        self.finished = False
        
        
    @staticmethod
    def clear_unused_timers():
        timers_to_keep = []
        for t in TimedObject.TIMED_OBJECT_LIST:
            if t.get_timer_type() == "debuff" and t.finished:
                continue
            timers_to_keep.append(t)
        TimedObject.TIMED_OBJECT_LIST = timers_to_keep
        Mob.ID = 0
        
    def on_cooldown_end(self):
        return
    
    def get_timer_type(self):
        return "base_timer"
        
    def start_cooldown(self):
        self.time_start = Arena.ARENA.time
        self.time_completed = 0
        self.on_cooldown = True
        self.finished = False
        
    def set_duration(self, duration):
        self.duration = duration
        
    def time_tic(self):
        self.time_completed += Arena.ARENA.tic_size * self.tic_rate
        if self.time_completed >= self.duration and self.on_cooldown:
            self.finished = True 
            self.on_cooldown = False
            self.on_cooldown_end()


class Mob:
    ID = 0
    DEBUFFS_APPLY_TO_ADDING_POWER = False
    def __init__(self, total_hp=10000, level_shift=0, base_resistance=BASE_RESISTANCES):
        self.starting_hp = total_hp
        self.total_hp = total_hp
        self.damage_taken = 0
        self.base_resistance = base_resistance
        self.debuffs = {}
        self.debuff_time_correction = {}
        self.alive = True
        self.time_alive = 0
        self.id = Mob.ID
        Mob.ID += 1
        self.level_shift = level_shift
        
        
    def print_data(self):
        print(f"Starting hp {self.starting_hp} damage taken {self.damage_taken} time alive {self.time_alive}")
        
        
    def get_level_shift_modifier(self):
        # https://homecoming.wiki/wiki/Purple_Patch
        level_shifts={-2: 1.22,
                      -1: 1.11,
                       0: 1,
                       1: .9,
                       2: .8,
                       3: .65,
                       4: .48}
        return level_shifts[self.level_shift]
        
        
    def get_resistance(self):
        resistance = deepcopy(self.base_resistance)
        debuffs_to_remove = []
        level_shift = self.get_level_shift_modifier()
        for name,debuff in self.debuffs.items():
            if debuff.finished:
                debuffs_to_remove.append(name)
                continue
            for rtype, mag in resistance.items():
                # https://homecoming.wiki/wiki/Resistance_(Mechanics)#Resistance_to_Resistance_Debuffs
                resistance[rtype] -= debuff() * level_shift * (1.-self.base_resistance[rtype])
            
        for name in debuffs_to_remove:
            del self.debuffs[name]
            
        return resistance
        
        
    def apply_new_debuffs(self, new_debuffs, timer_shift = 0):
        for debuff in new_debuffs:
            if debuff.name in self.debuffs:
                time_remaining = self.debuffs[debuff.name].duration - self.debuffs[debuff.name].time_completed
                time_correction = min(timer_shift, time_remaining)
                if debuff.name in self.debuff_time_correction:
                    self.debuff_time_correction[debuff.name] += time_correction
                else:
                    self.debuff_time_correction[debuff.name] = time_correction
            self.debuffs[debuff.name] = debuff
            self.debuffs[debuff.name].time_completed -= timer_shift
            self.debuffs[debuff.name].tic_rate = 1. / self.get_level_shift_modifier()
            self.debuffs[debuff.name].start_cooldown()
        
        
    def apply_power(self, power):
        self.time_alive = Arena.ARENA.time
        damage, new_debuffs = power()
        level_shift = self.get_level_shift_modifier()
        if Mob.DEBUFFS_APPLY_TO_ADDING_POWER: # apply new debuffs, then modify damage with debuffs
            self.apply_new_debuffs(new_debuffs)
            resistance = self.get_resistance()
        else: # modify damage with existing debuffs, then apply new debuffs
            resistance = self.get_resistance()
            # modify start time to match end of power activation
            timer_shift = power.cast_time * (1. / level_shift)
            self.apply_new_debuffs(new_debuffs)
        total_damage = 0
        for rtype in damage.keys():
            damage[rtype] *= (1. - resistance[rtype]) * level_shift
            total_damage += damage[rtype]
        #print(f"Total damage taken from power {power.name} is {total_damage:.02f} damage by type is {damage} resistance is {resistance}")
        if self.total_hp > 0:
            self.total_hp = self.total_hp - total_damage
        self.damage_taken += total_damage
        if self.total_hp <= 0 and self.alive:
            self.alive = False


class Debuff(TimedObject):
    def __init__(self, name, resistance):
        super().__init__(duration=10)
        self.resistance = resistance
        self.name = name
        
    def get_timer_type(self):
        return "debuff"
        
    def __call__(self):
        if not self.finished and self.on_cooldown:
            return self.resistance
        else:
            return damage


class Proc:
    def __init__(self, name, proc_type = 'damage', ppm = 3.5, damage = {"Energy":71.75}, debuff_mag=.2):
        self.type = proc_type
        self.ppm = ppm
        self.damage = damage
        self.name = name
        self.debuff_mag = debuff_mag
        
    def __call__(self):
        if self.type == 'damage':
            return self.damage
        else:
            debuff = Debuff(self.name, self.debuff_mag)
            return debuff


class Power(TimedObject):
    GLOBAL_RECHARGE = 0.
    def __init__(self,
                 damage,
                 recharge,
                 recharge_enhancement,
                 cast_time,
                 radius,
                 arc,
                 power_range,
                 max_targets,
                 name="",
                 is_pbaoe=False):
        super().__init__(duration=recharge, tic_rate=self.GLOBAL_RECHARGE + recharge_enhancement)
        self.recharge = recharge / recharge_enhancement
        self.cast_time = cast_time
        self.damage = damage
        self.dpa = np.sum([dmg / self.cast_time for dmg in damage.values()])
        self.radius = radius
        self.arc = arc
        self.range = power_range
        self.max_targets = max_targets
        self.name = name
        self.verbosity = 0
        self.proc_list = []
        self.is_pbaoe = is_pbaoe
        
        
    def area_factor(self):
        # from https://homecoming.wiki/wiki/Procs_Per_Minute
        if self.max_targets == 1:
            return 1.
        if self.arc != 360.:
            self.radius = self.range
        return (1. + 0.15 * self.radius - 0.011 * self.radius * (360 - self.arc) / 30.) * .75 + .25
    
    def get_timer_type(self):
        return "power"
        
        
    def proc_chance(self):
        chance = []
        for proc in self.proc_list:
            prob = proc.ppm * (self.recharge + self.cast_time) / (60 * self.area_factor())
            prob = min(.9, prob)
            prob = max(.05 + proc.ppm*.015, prob)
            chance.append(prob)
        return chance
    
    def on_cooldown_end(self):
        if self.verbosity  >= 1:
            print(f"Cooldown ended for power {self.name} at {Arena.ARENA.time:.03f}")
            
        
    def __call__(self):
        self.start_cooldown()
        total_damage = deepcopy(self.damage)
        proc_chance = self.proc_chance()
        debuff_list = []
        for idx, proc in enumerate(self.proc_list):
            proc_roll = Arena.ARENA.rng.uniform(0.,1.)
            #print(f"Proc {proc.name}! for {proc()}")
            if proc_roll <= proc_chance[idx]:
                if proc.type == 'damage':
                    proc_dmg = proc()
                    for dmg_type, mag in proc_dmg.items():
                        if dmg_type in total_damage:
                            total_damage[dmg_type] += mag
                        else:
                            total_damage[dmg_type] = mag
                            
                else:
                    debuff_list.append(proc())
                    
        return total_damage, debuff_list


class Hero:
    def __init__(self):
        self.powers = []
        self.cast_lockout = TimedObject(duration=1.)
        self.verbosity=0
        
        
    def set_powers(self, powers):
        self.powers = powers
        
        
    @staticmethod
    def power_priority(power):
        mobs_in_arena = len(Arena.ARENA.living_mobs)
        proc_dpa_modifier = 0
        proc_chances = power.proc_chance()
        for idx,proc in enumerate(power.proc_list):
            if proc.type == "damage":
                for mag in proc.damage.values():
                    proc_dpa_modifier += mag * proc_chances[idx]
        proc_dpa_modifier /= power.cast_time
        multiplier = min(power.max_targets, mobs_in_arena)
        return -1. *  multiplier * (power.dpa + proc_dpa_modifier)
        
        
    def set_power_priority(self):
        self.powers = sorted(self.powers,key=Hero.power_priority)
        
        
    def use_power(self, power, mob):
        self.cast_lockout.duration = power.cast_time
        self.cast_lockout.start_cooldown()
        mob.apply_power(power)
        
        
    def __call__(self):
        if self.cast_lockout.on_cooldown:
            return
        mob_list = Arena.ARENA.living_mobs
        self.set_power_priority()
        power_to_use = None
        has_power_available = False
        for p in self.powers:
            if not p.on_cooldown:
                power_to_use = p
                has_power_available = True
                break
        
        if not has_power_available:
            return
        
        if self.verbosity >=1:
            print(f"Activating power {power_to_use.name} at time {Arena.ARENA.time:.03f}")
        if power_to_use.max_targets > 1:
            if power_to_use.is_pbaoe:
                num_additional_targets = min(power_to_use.max_targets, len(mob_list))
                mobs_to_hit = Arena.ARENA.rng.choice(mob_list, num_additional_targets)
                for mob in mobs_to_hit:
                    self.use_power(power_to_use, mob)
            else:
                self.use_power(power_to_use,mob_list[0])
                num_additional_targets = min(power_to_use.max_targets - 1, len(mob_list) - 1)
                mobs_to_hit = Arena.ARENA.rng.choice(mob_list[1:], num_additional_targets)
                for mob in mobs_to_hit:
                    self.use_power(power_to_use, mob)
        else:
            self.use_power(power_to_use,mob_list[0])

