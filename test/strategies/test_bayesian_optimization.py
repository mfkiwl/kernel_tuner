import enum
import itertools
from re import L
from random import uniform as randfloat
import numpy as np
from collections import OrderedDict, namedtuple
from kernel_tuner.interface import Options
from kernel_tuner.strategies import minimize
from kernel_tuner.strategies import bayes_opt
from kernel_tuner.strategies.bayes_opt import BayesianOptimization

tune_params = OrderedDict()
tune_params["x"] = [1, 2, 3]
tune_params["y"] = [4, 5, 6]
tune_params["z"] = [7]

strategy_options = dict(popsize=0, max_fevals=10)
tuning_options = Options(dict(restrictions=[], tune_params=tune_params, strategy_options=strategy_options))
tuning_options["scaling"] = True
tuning_options["snap"] = True
max_threads = 1024

# initialize required data
parameter_space = list(itertools.product(*tune_params.values()))
_, _, eps = minimize.get_bounds_x0_eps(tuning_options, 1024)
original_to_normalized, normalized_to_original = bayes_opt.generate_normalized_param_dicts(tune_params, eps)
normalized_parameter_space = bayes_opt.normalize_parameter_space(parameter_space, tune_params, original_to_normalized)
pruned_parameter_space, removed_tune_params = bayes_opt.prune_parameter_space(normalized_parameter_space, tuning_options, tune_params, original_to_normalized)

# initialize BO
dev_dict = {
    'max_threads': max_threads
}
dev = namedtuple('Struct', dev_dict.keys())(*dev_dict.values())
runner_dict = {
    'dev': dev
}
runner = namedtuple('Struct', runner_dict.keys())(*runner_dict.values())
kernel_options = dict()
BO = BayesianOptimization(pruned_parameter_space, removed_tune_params, kernel_options, tuning_options, original_to_normalized, normalized_to_original, runner)
predictions, _, std = BO.predict_list(BO.unvisited_cache)


def test_generate_normalized_param_dicts():
    for parameter in tune_params:
        assert parameter in original_to_normalized.keys()
        assert parameter in normalized_to_original.keys()
        for o_n_value in original_to_normalized[parameter].values():
            assert o_n_value in normalized_to_original[parameter].keys()
            n_o_key = o_n_value
            n_o_value = normalized_to_original[parameter][n_o_key]
            o_n_key = n_o_value
            assert o_n_key == n_o_value
            assert n_o_key == o_n_value


def test_normalize_parameter_space():
    assert len(parameter_space) == len(normalized_parameter_space)
    for index in range(len(parameter_space)):
        assert len(parameter_space[index]) == len(normalized_parameter_space[index])


def test_prune_parameter_space():
    assert removed_tune_params == [None, None, list(normalized_to_original['z'].keys())[0]]
    for index in range(len(pruned_parameter_space)):
        assert len(pruned_parameter_space[index]) <= len(parameter_space[index])
        assert len(parameter_space[index]) - len(pruned_parameter_space[index]) == 1


def test_bo_initialization():
    assert BO.num_initial_samples == 0
    assert callable(BO.optimize)
    assert len(BO.results) == 0
    assert BO.searchspace == pruned_parameter_space
    assert BO.unvisited_cache == pruned_parameter_space
    assert len(BO.observations) == len(pruned_parameter_space)
    assert BO.current_optimum == np.PINF


def test_bo_is_better_than():
    BO.opt_direction = 'max'
    assert BO.is_better_than(2, 1)
    assert BO.is_better_than(-0.1, -0.2)
    BO.opt_direction = 'min'
    assert BO.is_better_than(1, 2)
    assert BO.is_better_than(-0.2, -0.1)


def test_bo_is_not_visited():
    for index, _ in enumerate(BO.searchspace):
        assert BO.is_not_visited(index)


def test_bo_get_af_by_name():
    for basic_af in ['ei', 'poi', 'lcb']:
        assert callable(BO.get_af_by_name(basic_af))


def test_bo_set_acquisition_function():
    BO.set_acquisition_function('multi-fast')
    assert callable(BO.optimize)


def test_bo_unvisited():
    assert BO.unvisited() == BO.unvisited_cache


def test_bo_find_param_config_index():
    for index, param_config in enumerate(BO.searchspace):
        assert BO.find_param_config_index(param_config) == index


def test_bo_de_normalize_param_config():
    for param_config in BO.searchspace:
        denormalized = BO.denormalize_param_config(param_config)
        normalized = BO.normalize_param_config(denormalized)
        assert param_config == normalized


def test_bo_unprune_param_config():
    for param_config in BO.searchspace:
        unpruned = BO.unprune_param_config(param_config)
        assert len(unpruned) - len(param_config) == 1


def test_bo_contextual_variance():
    BO.initial_sample_mean = 1.0
    assert isinstance(BO.contextual_variance(std), float)


def test_bo_observation_added():
    observations = list()
    for index, param_config in enumerate(BO.searchspace):
        observation = randfloat(0.1, 10)
        observations.append(observation)
        BO.update_after_evaluation(observation, index, param_config)
        assert BO.is_valid(observation)
        assert len(observations) == index + 1
        assert len(BO.unvisited_cache) == len(BO.searchspace) - index - 1
        assert BO.current_optimum == min(observations)
