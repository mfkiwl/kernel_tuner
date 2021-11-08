""" A simple greedy iterative local search algorithm for parameter search """

import itertools
import random

from kernel_tuner.strategies.minimize import _cost_func
from kernel_tuner import util
from kernel_tuner.strategies.greedy_mls import random_candidate
from kernel_tuner.strategies.hillclimbers import greedy_hillclimb

def tune(runner, kernel_options, device_options, tuning_options):
    """ Find the best performing kernel configuration in the parameter space

    :params runner: A runner from kernel_tuner.runners
    :type runner: kernel_tuner.runner

    :param kernel_options: A dictionary with all options for the kernel.
    :type kernel_options: kernel_tuner.interface.Options

    :param device_options: A dictionary with all options for the device
        on which the kernel should be tuned.
    :type device_options: kernel_tuner.interface.Options

    :param tuning_options: A dictionary with all options regarding the tuning
        process.
    :type tuning_options: kernel_tuner.interface.Options

    :returns: A list of dictionaries for executed kernel configurations and their
        execution times. And a dictionary that contains a information
        about the hardware/software environment on which the tuning took place.
    :rtype: list(dict()), dict()

    """

    dna_size = len(tuning_options.tune_params.keys())
    tune_params = tuning_options.tune_params

    options = tuning_options.strategy_options

    neighbour = options.get("neighbor", "Hamming")
    restart = options.get("restart", True)
    no_improvement = options.get("no_improvement", 50)
    randomwalk = options.get("random_walk", 0.3)
    perm_size = int(randomwalk * dna_size)
    if perm_size == 0:
        perm_size = 1
    max_fevals = options.get("max_fevals", 100)

    tuning_options["scaling"] = False

    # limit max_fevals to max size of the parameter space
    parameter_space = itertools.product(*tune_params.values())
    if tuning_options.restrictions is not None:
        parameter_space = filter(lambda p: util.check_restrictions(tuning_options.restrictions, p, tune_params.keys(), tuning_options.verbose), parameter_space)
    max_elems = len(list(parameter_space))
    if max_elems < max_fevals:
        max_fevals = max_elems

    fevals = 0
    max_threads = runner.dev.max_threads
    all_results = []
    unique_results = {}

    #while searching
    candidate = random_candidate(tune_params, tuning_options, max_threads)
    best_time = _cost_func(candidate, kernel_options, tuning_options, runner, all_results) 

    last_improvement = 0
    while fevals < max_fevals:
        candidate = greedy_hillclimb(candidate, restart, neighbour, max_fevals, all_results, unique_results, kernel_options, tuning_options, runner)

        fevals = len(unique_results)

        new_time = _cost_func(candidate, kernel_options, tuning_options, runner, all_results)
        # How to do maximization?
        if new_time < best_time:
            last_improvement = 0
            new_time = best_time
        else:
            last_improvement += 1
        
        # Instead of full restart, permute the starting candidate
        candidate = random_walk(candidate, perm_size, no_improvement, last_improvement, tune_params, tuning_options, max_threads)
    return all_results, runner.dev.get_environment()

def random_val(index, tune_params):
    """return a random value for a parameter"""
    key = list(tune_params.keys())[index]
    return random.choice(tune_params[key])

def point_mutate(dna, tune_params, tuning_options, max_threads):
    """Mutate DNA with 1/mutation_chance chance"""
    attempts = 50
    while attempts > 0:
        #decide which parameter to mutate
        i = random.choice(range(len(dna)))
        dna_out = dna[:]
        dna_out[i] = random_val(i, tune_params)

        if not dna_out == dna and util.config_valid(dna_out, tuning_options, max_threads):
            return dna_out
        attempts = attempts - 1
    return dna

def random_walk(indiv, permutation_size, no_improve, last_improve, tune_params, tuning_options, max_threads):
    if last_improve >= no_improve:
        return random_candidate(tune_params, tuning_options, max_threads)
    for k in range(permutation_size):
        indiv = point_mutate(indiv, tune_params, tuning_options, max_threads)
    return indiv
