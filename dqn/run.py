import argparse
import json
import copy
import os
import pickle
import random
import sys
import numpy as np
from agent_dqn import AgentDQN

from util import *
sys.path.append(os.getcwd())
sys.path.append(os.path.pardir)
from misc_scripts.access_django import *
from utils.lu import multi_turn_lu3
from utils.nlg import *
from user_simulator.usersim.usersim_rule import *
from django.db.models import Q
from crawler.models import *
from utils.query import *
from dialog_system import DialogManager
from dqn import dialog_config

"""
Launch a dialog simulation per the comm dand line arguments
This function instantiates a user_simulator, an agent, and a dialog system.
Next, it triggers the simulator to run for the specified number of episodes.
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    # Basic Environment Setup
    parser.add_argument('--act_set', dest='act_set', default="./dqn/dia_acts.txt", type=str,
                        help='path to dia act set; none for loading from labeled file')
    parser.add_argument('--slot_set', dest='slot_set', default="./dqn/slot_set.txt", type=str,
                        help='path to slot set; none for loading from labeled file')

    # Basic Parameters Setup
    parser.add_argument('--max_turn', dest='max_turn',
                        default=20, type=int, help='maximum length of each dialog (default=20, 0=no maximum length)')
    parser.add_argument('--episodes', dest='episodes',
                        default=50, type=int, help='Total number of episodes to run (default=1)')
    parser.add_argument('--slot_err_prob', dest='slot_err_prob',
                        default=0.00, type=float, help='the slot err probability')
    parser.add_argument('--slot_err_mode', dest='slot_err_mode',
                        default=0, type=int, help='slot_err_mode: 0 for slot_val only; 1 for three errs')
    parser.add_argument('--intent_err_prob', dest='intent_err_prob',
                        default=0.00, type=float, help='the intent err probability')
    parser.add_argument('--agt', dest='agt',
                        default=9, type=int, help='Select an agent: 0 for a command line input, 1-6 for rule based agents')
    parser.add_argument('--usr', dest='usr',
                        default=0, type=int, help='Select a user simulator. 0 is a Frozen user simulator.')
    parser.add_argument('--epsilon', dest='epsilon',
                        default=0.1, type=float, help='Epsilon to determine stochasticity of epsilon-greedy agent policies')
    parser.add_argument('--act_level', dest='act_level',
                        default=1,  type=int, help='0 for dia_act level; 1 for NL level')
    parser.add_argument('--run_mode', dest='run_mode',
                        default=3, type=int, help='run_mode: 0 for default NL; 1 for dia_act; 2 for both')
    parser.add_argument('--auto_suggest', dest='auto_suggest',
                        default=1,  type=int, help='0 for no auto_suggest; 1 for auto_suggest')
    parser.add_argument('--cmd_input_mode', dest='cmd_input_mode',
                        default=0, type=int, help='run_mode: 0 for NL; 1 for dia_act')

    # Load NLG & NLU Model
    # parser.add_argument('--nlg_model_path', dest='nlg_model_path', type=str,
    #                     default='./deep_dialog/models/nlg/lstm_tanh_relu_[1468202263.38]_2_0.610.p', help='path to model file')
    # parser.add_argument('--nlu_model_path', dest='nlu_model_path', type=str,
    #                     default='./deep_dialog/models/nlu/lstm_[1468447442.91]_39_80_0.921.p', help='path to the NLU model file')

    # RL-Agent Parameters
    parser.add_argument('--experience_replay_pool_size', dest='experience_replay_pool_size',
                        default=500, type=int, help='the size for experience replay')
    parser.add_argument('--batch_size', dest='batch_size',
                        default=20, type=int, help='batch size')
    parser.add_argument('--gamma', dest='gamma',
                        default=0.9, type=float, help='gamma for DQN')
    parser.add_argument('--predict_mode', dest='predict_mode',
                        default=False, type=bool, help='predict model for DQN')
    parser.add_argument('--simulation_epoch_size', dest='simulation_epoch_size',
                        default=50, type=int, help='the size of validation set')
    parser.add_argument('--warm_start', dest='warm_start',
                        default=1, type=int, help='0: no warm start; 1: warm start for training')
    parser.add_argument('--warm_start_epochs', dest='warm_start_epochs',
                        default=50, type=int, help='the number of epochs for warm start')
    parser.add_argument('--trained_model_path', dest='trained_model_path',
                        default=None, type=str, help='the path for trained model')
    parser.add_argument('-o', '--write_model_dir', dest='write_model_dir',
                        default='./dqn/checkpoints/', type=str, help='write model to disk')
    parser.add_argument('--save_check_point', dest='save_check_point',
                        default=10, type=int, help='number of epochs for saving model')
    parser.add_argument('--success_rate_threshold', dest='success_rate_threshold',
                        default=0.5, type=float, help='the threshold for success rate')
    # parser.add_argument('--split_fold', dest='split_fold',
                        #   default=5, type=int, help='the number of folders to split the user goal')
    parser.add_argument('--learning_phase', dest='learning_phase',
                        default='train', type=str, help='train/test/all; default is all')

    # RL-Model Parameters
    parser.add_argument('--learning_rate', dest='learning_rate',
                        default=1e-3, type=float, help='the learning rate of model')
    parser.add_argument('--momentum', dest='momentum',
                        default=0.1, type=float, help='the momentum value of optimizer')
    parser.add_argument('--grad_clip', dest='grad_clip',
                        default=-1e-3, type=float, help='the gradient limitation')
    parser.add_argument('--smooth_eps', dest='smooth_eps',
                        default=1e-8, type=float, help='smooth epsiolon value')
    parser.add_argument('--opt', dest='opt',
                        default='adam', type=str, help='the model optimizer')
    parser.add_argument('--dropout_rate', dest='dropout_rate',
                        default=0.2, type=float, help='dropout rate between layers')
    parser.add_argument('--activation_func', dest='activation_func',
                        default='relu', type=str, help='the model layers\' activation functions')

    args = parser.parse_args()
    params = vars(args)


all_courses = list(query_course({}).values())
np.random.shuffle(all_courses)
course_dict = {k: v for k, v in enumerate(all_courses)}
act_set = text_to_dict(params['act_set'])
slot_set = text_to_dict(params['slot_set'])
print("=============== Data Pre-processing Done\n")

##########################################################################
#   @params run_mode: (type: int)
#       0   for display mode (NL)
#       1   for debug mode(Dia_Act)
#       2   for debug mode(Dia_Act and NL)
#       >=3 for no display(i.e. training)
#   @params auto_suggest: (type: int)
#       0   for no auto_suggest
#       1   for auto_suggest
##########################################################################
dialog_config.run_mode = params['run_mode']
dialog_config.auto_suggest = params['auto_suggest']
print("=============== Dialog Configurations Setup Done\n")

##########################################################################
# Parameters for RL-Model (Deep-Q-Network)
#   @params model_params: parameters of model (type: dict)
#       @params lr: learning rate (type: float)
#       @params moment: momentum value of optimizer (type: float, optional)
#       @params grad_clip: gradient limitation (type: float, optional)
#       @params smooth_eps: smooth epsiolon value (type: float, optional)
#       @params opt: model optimizer (type: string)
#       @params dp: dropout rate between layers (type: float)
#       @params activation_func: model layers activation function (type: string)
##########################################################################
model_params = {}
model_params['learning_rate'] = params['learning_rate']
model_params['momentum'] = params['momentum']
model_params['grad_clip'] = params['grad_clip']
model_params['smooth_eps'] = params['smooth_eps']
model_params['opt'] = params['opt']
model_params['dropout_rate'] = params['dropout_rate']
model_params['activation_func'] = params['activation_func']
print("=============== Model Setup Done\n")

##########################################################################
# Parameters for Agent (Deep-Q-Network Agent)
#   @params agent_params: parameters of agent (type: dict)
#       @params act_level: (type: int)
#           0   for user simulator is Dia_Act level
#           1   for user simulator is NL level
#       @params predict_mode: predict model for DQN (type: bool)
#       @params warm_start: (type: int)
#           use rule policy to fill the experience-replay pool at the beginning
#           0   no warm start
#           1   warm start for training
#       @params cmd_input_mode: (type: int)
#           0   for NL input
#           1   for Dia_Act input (this parameter is for AgentCmd only)
##########################################################################
agt = params['agt']
agent_params = {}
agent_params['max_turn'] = params['max_turn']
agent_params['epsilon'] = params['epsilon']
agent_params['agent_run_mode'] = params['run_mode']
agent_params['agent_act_level'] = params['act_level']
agent_params['experience_replay_pool_size'] = params['experience_replay_pool_size']
agent_params['batch_size'] = params['batch_size']
agent_params['gamma'] = params['gamma']
agent_params['predict_mode'] = params['predict_mode']
agent_params['trained_model_path'] = params['trained_model_path']
agent_params['warm_start'] = params['warm_start']
agent_params['cmd_input_mode'] = params['cmd_input_mode']
agent_params['model_params'] = model_params
agent = AgentDQN(course_dict, act_set, slot_set, agent_params)
print("=============== RL-Agent (DQN) Setup Done\n")

##########################################################################
# Parameters for User Simulators
#   @params usersim_params: parameters of user simulator (type: dict)
#   @params slot_err_prob: slot level error probability (type: float)
#   @params slot_err_mode: which kind of slot err mode (type: int)
#       0   for slot_val only
#       1   for three errs
#   @params intent_err_prob: intent level error probability (type: float)
#   @params learning_phase: train/test/all, default is all. (type: str)
#                           The user goal set could be split into train and
#                           test set, or do not split (all). Here exists
#                           some randomness at the first sampled user action,
#                           even for the same user goal, the generated
#                           dialogue might be different
#       'all'     train + test
#       'train'   train only
#       'test'    test only
##########################################################################
usr = params['usr']
usersim_params = {}
usersim_params['max_turn'] = params['max_turn']
usersim_params['slot_err_probability'] = params['slot_err_prob']
usersim_params['slot_err_mode'] = params['slot_err_mode']
usersim_params['intent_err_probability'] = params['intent_err_prob']
usersim_params['simulator_run_mode'] = params['run_mode']
usersim_params['simulator_act_level'] = params['act_level']
usersim_params['learning_phase'] = params['learning_phase']
user_sim = RuleSimulator(all_courses)
# user_sim = RuleSimulator(course_dict, act_set, slot_set, usersim_params)
print("=============== RuleSimulator Setup Done\n")

##########################################################################
# load trained NLG model (need to be transformed)
##########################################################################
# nlg_model_path = params['nlg_model_path']
# diaact_nl_pairs = params['diaact_nl_pairs']
# nlg_model = nlg()
# nlg_model.load_nlg_model(nlg_model_path)
# nlg_model.load_predefine_act_nl_pairs(diaact_nl_pairs)

# agent.set_nlg_model(nlg_model)
# user_sim.set_nlg_model(nlg_model)

##########################################################################
# load trained NLU model (need to be transformed)
##########################################################################
# nlu_model_path = params['nlu_model_path']
# nlu_model = nlu()
# nlu_model.load_nlu_model(nlu_model_path)

# agent.set_nlu_model(nlu_model)
# user_sim.set_nlu_model(nlu_model)

##########################################################################
# Dialog Manager
##########################################################################
dialog_manager = DialogManager(agent, user_sim, act_set, slot_set, course_dict, all_courses)
print("=============== DialogManager Setup Done\n")

##########################################################################
#   Run num_episodes Conversation Simulations
##########################################################################
status = {'successes': 0, 'count': 0, 'cumulative_reward': 0}
simulation_epoch_size = params['simulation_epoch_size']
batch_size = params['batch_size']
warm_start = params['warm_start']
warm_start_epochs = params['warm_start_epochs']
success_rate_threshold = params['success_rate_threshold']
save_check_point = params['save_check_point']
print("=============== Parameters Setup Done\n")

""" Initialization of Best Model and Performance Records """
best_model = {}
best_res = {'avg_reward': float('-inf'), 'epoch': 0,
            'avg_turns': float('inf'),   'success_rate': 0}
# best_model['model'] = copy.deepcopy(agent)
best_res['success_rate'] = 0
performance_records = {}
performance_records['success_rate'] = {}
performance_records['avg_turns'] = {}
performance_records['avg_reward'] = {}
print("=============== Performance Records Setup Done\n")


""" Save Keras Model """
def save_keras_model(path, agt, success_rate, best_epoch, cur_epoch):
    filename = 'agt_%s_%s_%s_%.5f' % (agt, best_epoch, cur_epoch, success_rate)
    filepath = os.path.join(path, filename)
    checkpoint = {}
    checkpoint['params'] = params
    try:
        with open(filepath + '.p', 'wb') as f:
            pickle.dump(checkpoint, f, protocol=pickle.HIGHEST_PROTOCOL)
        dialog_manager.agent.model.save(filepath + '.h5')
        print('Success! save_keras_model: Model saved in %s' % (filepath, ))
    except Exception as e:
        print('Error! save_keras_model: Writing model fails: %s' % filepath)
        print('\t', e)

""" Save Performance Numbers """
def save_performance_records(path, agt, records):
    filename = 'agt_%s_performance_records.json' % (agt)
    filepath = os.path.join(path, filename)
    try:
        json.dump(records, open(filepath, "w"))
        print('Success! save_performance_records: Model saved in %s' % (filepath, ))
    except Exception as e:
        print('Error! save_performance_records: Writing model fails: %s' % filepath)
        print('\t', e)


""" Warm_Start Simulation (by Rule Policy) """
def warm_start_simulation(warm_start_epochs):
    successes = 0
    cumulative_reward = 0
    cumulative_turns = 0

    res = {}
    for episode in range(warm_start_epochs):
        print("================Episode %3d Start================" % episode)
        dialog_manager.initialize_episode()
        episode_over = False
        per_episode_reward = 0
        while not episode_over:
            episode_over, reward = dialog_manager.next_turn()
            cumulative_reward += reward
            per_episode_reward += reward
            if episode_over:
                if reward > 0:
                    successes += 1
                    print("Warm Start Simulation Episode %3d: Success\t(Reward: %+.5f, #Turns: %2d)"
                          % (episode, per_episode_reward, dialog_manager.state_tracker.turn_count))
                else:
                    print("Warm Start Simulation Episode %3d: Fail\t\t(Reward: %+.5f, #Turns: %2d)"
                          % (episode, per_episode_reward, dialog_manager.state_tracker.turn_count))
                cumulative_turns += dialog_manager.state_tracker.turn_count

        if len(agent.experience_replay_pool) >= agent.experience_replay_pool_size:
            break

        print("================Episode %3d Over!================\n" % episode)

    agent.warm_start = 2  # just a counter to avoid executing warm simulation twice
    res['success_rate'] = float(successes) / warm_start_epochs
    res['avg_reward'] = float(cumulative_reward) / warm_start_epochs
    res['avg_turns'] = float(cumulative_turns) / warm_start_epochs
    print("\"Warm Start Simulation\":"
          "\n\t#Epoch: %s"
          "\n\tSuccess Rate: %s"
          "\n\tAvg Reward: %s"
          "\n\tAvg Turns:  %s" % (episode + 1, res['success_rate'], res['avg_reward'], res['avg_turns']))
    print("\n\tCurrent Experience-Replay Pool Size: %s" %
          (len(agent.experience_replay_pool)), '\n')


""" Run N-Simulation Dialogues """
def simulation_epoch(simulation_epoch_size):
    successes = 0
    cumulative_reward = 0
    cumulative_turns = 0

    res = {}
    for episode in range(simulation_epoch_size):
        print("================Episode %3d Start================" % episode)
        dialog_manager.initialize_episode()
        episode_over = False
        per_episode_reward = 0
        while not episode_over:
            episode_over, reward = dialog_manager.next_turn()
            cumulative_reward += reward
            per_episode_reward += reward
            if episode_over:
                if reward > 0:
                    successes += 1
                    print("Simulation Episode %3d: Success\t(Reward: %+.5f, #Turns: %2d)"
                          % (episode, per_episode_reward, dialog_manager.state_tracker.turn_count))
                else:
                    print("Simulation Episode %3d: Fail\t(Reward: %+.5f, #Turns: %2d)"
                          % (episode, per_episode_reward, dialog_manager.state_tracker.turn_count))
                cumulative_turns += dialog_manager.state_tracker.turn_count

        print("================Episode %3d Over!================\n" % episode)

    res['success_rate'] = float(successes) / simulation_epoch_size
    res['avg_reward'] = float(cumulative_reward) / simulation_epoch_size
    res['avg_turns'] = float(cumulative_turns) / simulation_epoch_size
    print("\"Simulation Epoch\":"
          "\n\t#Epoch: %s"
          "\n\tSimulation Success Rate: %s"
          "\n\tAvg Reward: %s"
          "\n\tAvg Turns:  %s" % (episode + 1, res['success_rate'], res['avg_reward'], res['avg_turns']))
    print("\n\tCurrent Experience-Replay Pool Size: %s" %
          (len(agent.experience_replay_pool)), '\n')
    return res


""" Run Episodes """
def run_episodes(count, status):
    successes = 0
    cumulative_reward = 0
    cumulative_turns = 0

    # if params['trained_model_path'] == None and warm_start == 1:
    if warm_start == 1:
        print('Warm Start Starting ...\n')
        warm_start_simulation(warm_start_epochs)
        print('Warm Start Finished, Start RL Training ...\n')

    for episode in range(count):
        print("Episode: %s" % (episode))
        dialog_manager.initialize_episode()
        episode_over = False
        per_episode_reward = 0
        while not episode_over:
            episode_over, reward = dialog_manager.next_turn()
            cumulative_reward += reward
            per_episode_reward += reward
            if episode_over:
                if reward > 0:
                    print("Successful Dialog! (Reward: %s)" % per_episode_reward)
                    successes += 1
                else:
                    print("Failed Dialog! (Reward: % s)" % per_episode_reward)

                cumulative_turns += dialog_manager.state_tracker.turn_count

    # Run Simulation
    # if params['trained_model_path'] == None:
        agent.predict_mode = True
        print("Get Simulation Results......")
        simulation_res = simulation_epoch(simulation_epoch_size)

        performance_records['success_rate'][episode] = simulation_res['success_rate']
        performance_records['avg_reward'][episode] = simulation_res['avg_reward']
        performance_records['avg_turns'][episode] = simulation_res['avg_turns']

        if simulation_res['success_rate'] >= success_rate_threshold:  # threshold = 0.90
            if simulation_res['success_rate'] >= best_res['success_rate']:
                agent.experience_replay_pool = [] # clear the exp-pool by better dialogues
                simulation_epoch(simulation_epoch_size)
            else:
                if random.random() < agent.epsilon:
                    agent.experience_replay_pool = [] # clear the exp-pool by better dialogues
                    simulation_epoch(simulation_epoch_size)

        if simulation_res['success_rate'] > best_res['success_rate']:
            best_res['success_rate'] = simulation_res['success_rate']
            best_res['avg_reward'] = simulation_res['avg_reward']
            best_res['avg_turns'] = simulation_res['avg_turns']
            best_res['epoch'] = episode

        agent.train(batch_size, 1)
        agent.predict_mode = False

        print("Simulation Success Rate %s, Avg Reward %s, Avg Turns %s, Best Success Rate %s"
                % (performance_records['success_rate'][episode],
                   performance_records['avg_reward'][episode],
                   performance_records['avg_turns'][episode],
                   best_res['success_rate']))

        # save the model every 10 episodes
        if episode % save_check_point == 0 and params['trained_model_path'] == None:
            save_keras_model(params['write_model_dir'], agt,
                             best_res['success_rate'], best_res['epoch'], episode)
            save_performance_records(params['write_model_dir'], agt, performance_records)

        print("Progress: %s / %s, Success rate: %s / %s Avg reward: %.3f Avg turns: %.3f\n" %
                (episode + 1, count, successes, episode + 1, float(cumulative_reward) / (episode + 1), float(cumulative_turns) / (episode + 1)))

    print("Final Success rate: %s / %s Avg reward: %.3f Avg turns: %.3f" %
                (successes, count, float(cumulative_reward) / count, float(cumulative_turns) / count))
    status['successes'] += successes
    status['count'] += count

    # if params['trained_model_path'] == None:
    save_keras_model(params['write_model_dir'], agt, float(successes) / count, best_res['epoch'], count)
    save_performance_records(params['write_model_dir'], agt, performance_records)


run_episodes(500, status)
