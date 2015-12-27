#!/usr/bin/env python2
# -*- coding: UTF-8 -*-
# File: train.py
# Author: Yuxin Wu <ppwwyyxx@gmail.com>

import tensorflow as tf
from utils import *
from dataflow import DataFlow
from itertools import count
import argparse

def prepare():
    keep_prob = tf.placeholder(
        tf.float32, shape=tuple(), name=DROPOUT_PROB_OP_NAME)
    global_step_var = tf.Variable(
        0, trainable=False, name=GLOBAL_STEP_OP_NAME)


def start_train(config):
    """
    Start training with the given config
    Args:
        config: a tensorpack config dictionary
    """
    dataset_train = config['dataset_train']
    assert isinstance(dataset_train, DataFlow), dataset_train.__class__

    # a tf.train.Optimizer instance
    optimizer = config['optimizer']
    assert isinstance(optimizer, tf.train.Optimizer), optimizer.__class__

    # a list of Callback instance
    callbacks = Callbacks(config.get('callbacks', []))

    # a tf.ConfigProto instance
    sess_config = config.get('session_config', None)
    assert isinstance(sess_config, tf.ConfigProto), sess_config.__class__

    # a list of input/output variables
    input_vars = config['inputs']
    output_vars = config['outputs']
    cost_var = config['cost']

    max_epoch = int(config['max_epoch'])

    # build graph
    G = tf.get_default_graph()
    for v in input_vars:
        G.add_to_collection(INPUT_VARS_KEY, v)
    for v in output_vars:
        G.add_to_collection(OUTPUT_VARS_KEY, v)
    summary_model()

    global_step_var = G.get_tensor_by_name(GLOBAL_STEP_VAR_NAME)

    # add some summary ops to the graph
    averager = tf.train.ExponentialMovingAverage(
        0.9, num_updates=global_step_var, name='avg')
    vars_to_summary = [cost_var] + \
            tf.get_collection(SUMMARY_VARS_KEY) + \
            tf.get_collection(COST_VARS_KEY)
    avg_maintain_op = averager.apply(vars_to_summary)
    for c in vars_to_summary:
        tf.scalar_summary(c.op.name, averager.average(c))

    # maintain average in each step
    with tf.control_dependencies([avg_maintain_op]):
        grads = optimizer.compute_gradients(cost_var)

    for grad, var in grads:
        if grad:
            tf.histogram_summary(var.op.name + '/gradients', grad)

    train_op = optimizer.apply_gradients(grads, global_step_var)

    sess = tf.Session(config=sess_config)
    # start training
    with sess.as_default():
        sess.run(tf.initialize_all_variables())
        callbacks.before_train()

        keep_prob_var = G.get_tensor_by_name(DROPOUT_PROB_VAR_NAME)
        for epoch in xrange(1, max_epoch):
            with timed_operation('epoch {}'.format(epoch)):
                for dp in dataset_train.get_data():
                    feed = {keep_prob_var: 0.5}
                    feed.update(dict(zip(input_vars, dp)))

                    results = sess.run(
                        [train_op, cost_var] + output_vars, feed_dict=feed)
                    cost = results[1]
                    outputs = results[2:]
                    callbacks.trigger_step(feed, outputs, cost)

                callbacks.trigger_epoch()

def main(get_config_func):
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpu', help='GPU(s) to use.') # nargs='*' in multi mode
    args = parser.parse_args()
    device = '/cpu:0'
    if args.gpu:
        device = '/gpu:{}'.format(args.gpu)

    with tf.Graph().as_default():
        with tf.device(device):
            prepare()
            config = get_config_func()
            start_train(config)
