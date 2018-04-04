import numpy as np
import argparse
import tensorflow as tf
import matplotlib.pyplot as plt
from sklearn.utils import shuffle
from sklearn.model_selection import StratifiedKFold
import math
from datetime import datetime

NUM_LABELS = 47
rnd = np.random.RandomState(123)
tf.set_random_seed(123)


BATCH_SIZE = 256

#MODEL_NAME = ""
CNN_MODEL_PATH = "../checkpoints/cnn_model"

# Following functions are helper functions that you can feel free to change
def convert_image_data_to_float(image_raw):
    img_float = tf.expand_dims(tf.cast(image_raw, tf.float32) / 255, axis=-1)
    return img_float


def visualize_ae(i, x, features, reconstructed_image):
    '''
    This might be helpful for visualizing your autoencoder outputs
    :param i: index
    :param x: original data
    :param features: feature maps
    :param reconstructed_image: autoencoder output
    :return:
    '''
    plt.figure(0)
    plt.imshow(x[i, :, :], cmap="gray")
    plt.figure(1)
    plt.imshow(reconstructed_image[i, :, :, 0], cmap="gray")
    plt.figure(2)
    plt.imshow(np.reshape(features[i, :, :, :], (7, -1), order="F"), cmap="gray",)

def build_cnn_model(placeholder_x, placeholder_y):
    with tf.variable_scope("cnn") as scope:

        img_float = convert_image_data_to_float(placeholder_x)
        #input_layer = tf.reshape(img_float, [-1, 28, 28, 1])
        #conv1
        w_conv1 = tf.get_variable("conv1_weight", shape=(3, 3, 1, 32),
                                  initializer=tf.contrib.layers.xavier_initializer())
        b_conv1 = tf.get_variable("conv1_bias", shape=(32), initializer=tf.contrib.layers.xavier_initializer())
        y_conv1 = tf.nn.conv2d(img_float, w_conv1, strides=[1, 1, 1, 1], padding='SAME') + b_conv1
        conv1= tf.nn.relu(y_conv1)
        #conv2
        w_conv2 = tf.get_variable("conv2_weight", shape=(5,5,32,32), initializer=tf.contrib.layers.xavier_initializer())
        b_conv2 = tf.get_variable("conv2_bias", shape=(32), initializer=tf.contrib.layers.xavier_initializer())
        y_conv2 = tf.nn.conv2d(conv1, w_conv2, strides=[1,2,2,1], padding='SAME') + b_conv2
        conv2 = tf.nn.relu(y_conv2)
        #conv3
        w_conv3 = tf.get_variable("conv3_weight", shape=(3,3,32,64), initializer=tf.contrib.layers.xavier_initializer())
        b_conv3 = tf.get_variable("conv3_bias", shape=(64), initializer=tf.contrib.layers.xavier_initializer())
        y_conv3 = tf.nn.conv2d(conv2, w_conv3, strides=[1,1,1,1], padding='SAME') + b_conv3
        conv3 = tf.nn.relu(y_conv3)
        #conv 4
        w_conv4 = tf.get_variable("conv4_weight", shape=(5,5,64,64), initializer=tf.contrib.layers.xavier_initializer())
        b_conv4 = tf.get_variable("conv4_bias", shape=(64), initializer=tf.contrib.layers.xavier_initializer())
        y_conv4 = tf.nn.conv2d(conv3, w_conv4, strides=[1,2,2,1], padding='SAME') + b_conv4
        conv4 = tf.nn.relu(y_conv4)

        # Flatten
        features_flattened = tf.reshape(conv4, [-1, np.prod(conv4.shape[1:])])

        # FC Layer
        w_fc = tf.get_variable("fc_weight", shape=(features_flattened.shape[1], NUM_LABELS),
                                 initializer=tf.contrib.layers.xavier_initializer())
        logits = tf.matmul(features_flattened, w_fc)
        # loss
        loss = tf.losses.sparse_softmax_cross_entropy(labels=placeholder_y, logits=logits)

        params = [w_conv1, b_conv1, w_conv2, b_conv2, w_conv3, b_conv3, w_conv4, b_conv4, w_fc]

        #optimizeation, SGD with momentum, learning rate decay after x epoch
        #test 1: simple high-level simple SGD with momentum, learning rate fixed in each step.
        learning_rate = 0.001
        momentum = 0.9
        optimizer = tf.train.MomentumOptimizer(learning_rate,momentum)
        train_op = optimizer.minimize(loss, global_step = tf.train.get_global_step())
        #calc accuracy
        predictions = tf.argmax(logits, 1)
        one_hot_y = tf.one_hot(placeholder_y, NUM_LABELS)
        correct_prediction = tf.equal(predictions, tf.argmax(one_hot_y, 1))
        correct_cnt =  tf.reduce_sum(tf.cast(correct_prediction, tf.int32)) #tf.reduce_mean(tf.cast(correct_prediction, tf.float31))
        #acc, acc_op = tf.metrics.accuracy(placeholder_y, predictions) #TODO: this API seems to give a wrong answer in debugging.

        return params, train_op, loss, correct_cnt,predictions



def build_linear_model(placeholder_x,placeholder_y):
    with tf.variable_scope("linear") as scope:
        img_float = convert_image_data_to_float(placeholder_x)

        # This is a simple fully connected network
        img_flattened = tf.reshape(img_float,[-1,np.prod(placeholder_x.shape[1:])])
        weight = tf.get_variable("fc_weight",shape=(img_flattened.shape[1],NUM_LABELS),
                                 initializer=tf.random_normal_initializer(stddev=0.01))
        logits = tf.matmul(img_flattened, weight)
        loss = tf.losses.sparse_softmax_cross_entropy(
            labels=placeholder_y, logits=logits)

        # gradient decent algorithm
        params = [weight]
        learning_rate = 0.001
        grad = tf.gradients(loss, weight)[0]
        train_op = tf.assign_add(weight, -learning_rate * grad)

        #calc accuracy
        predictions = tf.argmax(logits, 1)
        one_hot_y = tf.one_hot(placeholder_y, NUM_LABELS)
        correct_prediction = tf.equal(predictions, tf.argmax(one_hot_y, 1))
        correct_cnt =  tf.reduce_sum(tf.cast(correct_prediction, tf.int32)) #tf.reduce_mean(tf.cast(correct_prediction, tf.float31))
        #acc, acc_op = tf.metrics.accuracy(placeholder_y, predictions)

    return params, train_op, loss, correct_cnt, predictions


# Major interfaces
def train_cnn(x, y, placeholder_x, placeholder_y):
    #TODO: 10 for debug
    #x = x[0:10]
    #y = y[0:10]

    NUM_ITERATIONS= 10
    NUM_BATCHES = int(math.ceil(x.shape[0]/BATCH_SIZE)) #ceil, make sure to ultilize all the data
    print("num_batches:", NUM_BATCHES)

    params, train_op, loss, correct_cnt, predictions = build_cnn_model(placeholder_x, placeholder_y)
    cnn_saver = tf.train.Saver(var_list=params)


    # 1) sample-1: for cross-validation, split into 5-fold.
    skf = StratifiedKFold(n_splits=2, random_state=10, shuffle=True)
    for train_index, validation_index in skf.split(x, y):
            print("TRAIN:", train_index, "TEST:", validation_index)
            x_train, y_train = x[train_index],y[train_index]
            x_validate, y_validate = x[validation_index],y[validation_index]

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        sess.run(tf.local_variables_initializer())
        start_time = datetime.now()
        print("Start training  {}".format(start_time))
        for epoch in range(NUM_ITERATIONS):
            # 1) sample-2: shuffle with fixed random seed in each epoch and split into batches. TODO: it's not efficiency to copy data in each epoch. indexing is more efficient.
            shuffledX, shuffledY = shuffle(x_train, y_train, random_state=epoch)
            loss_val= 0.0; acc_val= 0.0; num_trained_sample = 0; end_time={}

            for bi  in range(NUM_BATCHES):
                batch_x = shuffledX[bi * BATCH_SIZE : (bi+1)*BATCH_SIZE]
                batch_y = shuffledY[bi * BATCH_SIZE : (bi+1)*BATCH_SIZE]
                feed_dict = {placeholder_x: batch_x, placeholder_y: batch_y}
                #2) training
                _,loss_batch, correct_batch , pred_val = sess.run([train_op, loss, correct_cnt, predictions],  feed_dict=feed_dict)

                loss_val += loss_batch # loss.eval(feed_dict = feed_dict)
                acc_val += correct_batch # add up the number of correct predictions in each batch
                num_trained_sample += batch_x.shape[0] #secure, since it may not equal to NUM_BATCHES * BATCH_SIZE
                #print("debug: ",  batch_y, pred_val, acc_batch)

            end_time[epoch] = datetime.now()
            acc_val = acc_val/num_trained_sample
            loss_val = loss_val/NUM_BATCHES
            print("{}: Epoch {} finished , loss: {:.4f}, acc: {:.4f}".format(end_time[epoch], epoch, loss_val, acc_val))
            # 3) validate and save every 5 epoches
            if(epoch>2):
                cnn_saver.save(sess=sess, save_path=CNN_MODEL_PATH, global_step=epoch)


def test_cnn(x, y, placeholder_x, placeholder_y):
    # TODO: implement CNN testing
    params, train_op, loss, acc_op = build_cnn_model(placeholder_x, placeholder_y)
    with tf.Session() as sess:
        #saver = tf.train.import_meta_graph(CNN_MODEL_PATH + "-4.meta")
        saver = tf.train.Saver()
        saver.restore(sess,tf.train.latest_checkpoint("../checkpoints/"))
        #saver.restore(sess, "../checkpoints/cnn_model-3") # select the model generated in epoch 3
        #print(tf.train.latest_checkpoint("../checkpoints/"))

        NUM_BATCHES = int(x.shape[0]/BATCH_SIZE)
        loss_val = 0; acc_val=0;num_trained_sample=0
        for bi in range(NUM_BATCHES):
            batch_x = x[bi * BATCH_SIZE : (bi+1)*BATCH_SIZE]
            batch_y = y[bi * BATCH_SIZE : (bi+1)*BATCH_SIZE]
            feed_dict = {placeholder_x: batch_x, placeholder_y: batch_y}

            loss_cur, acc_cur = sess.run([loss, acc_op],feed_dict=feed_dict)

            loss_val += loss_cur
            acc_val += acc_cur
            num_trained_sample += batch_x.shape[0]

        result_accuracy = acc_val/num_trained_sample

    return result_accuracy


def train_ae(x, placeholder_x):
    # TODO: implement autoencoder training
    raise NotImplementedError


def evaluate_ae(x,placeholder_x):
    # TODO: evaluate your autoencoder
    raise NotImplementedError


def main():
    parser = argparse.ArgumentParser(description='COMP5212 Programming Project 2')
    parser.add_argument('--task', default="train_cnn", type=str,
                        help='Select the task, train_cnn, test_cnn, '
                             'train_ae, evaluate_ae, ')
    parser.add_argument('--datapath',default="./data",type=str, required=False,
                        help='Select the path to the data directory')
    args = parser.parse_args()
    datapath = args.datapath
    # TODO: for debug
    datapath = "../datasets"
    #args.task ="train_cnn"
    # set up the input image size, create the correspond place holder.
    with tf.variable_scope("placeholders"):
        img_var = tf.placeholder(tf.uint8, shape=(None, 28, 28), name="img")
        label_var = tf.placeholder(tf.int32, shape=(None,), name="true_label")

    if args.task == "train_cnn":
        file_train = np.load(datapath+"/data_classifier_train.npz")
        x_train = file_train["x_train"]
        y_train = file_train["y_train"]
        train_cnn(x_train, y_train, img_var, label_var)

    elif args.task == "test_cnn":
        file_test = np.load(datapath+"/data_classifier_test.npz")
        x_test = file_test["x_test"]
        y_test = file_test["y_test"]
        accuracy = test_cnn(x_test, y_test,img_var,label_var)
        print("accuracy = {}\n".format(accuracy))
    elif args.task == "train_ae":
        file_unsupervised = np.load(datapath + "/data_autoencoder_train.npz")
        x_ae_train = file_unsupervised["x_ae_train"]
        train_ae(x_ae_train, img_var)
    elif args.task == "evaluate_ae":
        file_unsupervised = np.load(datapath + "/data_autoencoder_eval.npz")
        x_ae_eval = file_unsupervised["x_ae_eval"]
        evaluate_ae(x_ae_eval, img_var)


if __name__ == "__main__":
    main()