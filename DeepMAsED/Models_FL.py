# import
## batteries
import logging
## 3rd party
import numpy as np
import keras
from keras.models import Model, Sequential
from keras.layers import Input, BatchNormalization
from keras.layers import GlobalMaxPooling1D, GlobalAveragePooling1D, concatenate
from keras.layers import Conv1D, Conv2D, Dropout, Dense
## application
from DeepMAsED import Utils


class deepmased(object):
    """
    Implements a convolutional network for misassembly prediction. 
    """
    def __init__(self, config):
        self.max_len = config.max_len
        self.filters = config.filters
        self.n_conv = config.n_conv
        self.n_features = config.n_features
        self.pool_window = config.pool_window
        self.dropout = config.dropout
        self.lr_init = config.lr_init
        self.n_fc = config.n_fc
        self.n_hid = config.n_hid

        #self.net = Sequential()
        inlayer = Input(shape=(None, self.n_features), name='input')

        x = Conv1D(self.filters, kernel_size=(5), 
                            input_shape=(None, self.n_features),
                            activation='relu', padding='valid', name='1st_conv')(inlayer)
        x = BatchNormalization(axis=-1)(x)

        for i in range(1, self.n_conv-1):
            x = Conv1D(2 ** i * self.filters, kernel_size=(3), 
                                strides=1, dilation_rate=2,
                                activation='relu')(x)
            x = BatchNormalization(axis=-1)(x)
            
        x = Conv1D(2 ** self.n_conv * self.filters, kernel_size=(3), 
                    strides=1, dilation_rate=2,
                    activation='relu')(x)
        x = BatchNormalization(axis=-1)(x)
        
        maxP = GlobalMaxPooling1D()(x)
        avgP = GlobalAveragePooling1D()(x)
        x = concatenate([maxP, avgP])

        optimizer = keras.optimizers.adam(lr=self.lr_init)

        for _ in range(1):
            x = Dense(self.n_hid, activation='relu')(x)
            x = Dropout(rate=self.dropout)(x)

        x = Dense(1, activation='sigmoid')(x)

        self.net =  Model(inputs=inlayer,outputs=x)
        self.net.compile(loss='binary_crossentropy',
                         optimizer=optimizer,
                         metrics=[Utils.class_recall_0, Utils.class_recall_1])


        self.reduce_lr = keras.callbacks.ReduceLROnPlateau(
                               monitor='val_loss', factor=0.5,
                               patience=5, min_lr = 0.01 * self.lr_init)

    def predict(self, x):
        return self.net.predict(x)

    def predict_generator(self, x):
        return self.net.predict_generator(x)

    def print_summary(self):
        print(self.net.summary())

    def save(self, path):
        self.net.save(path)


class Generator(keras.utils.Sequence):
    def __init__(self, x, y, max_len=10000, batch_size=32,
                 shuffle=True, norm_raw=True,
                 mean_tr=None, std_tr=None): 
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.max_len = max_len
        self.x = x
        self.y = y
        self.shuffle = shuffle
        self.n_feat = x[0].shape[1]

        if mean_tr is None:
            mean, std = Utils.compute_mean_std(self.x)
            self.mean = mean
            self.std = std
            if not norm_raw:
                self.mean[0:4] = 0
                self.std[0:4] = 1
        else:
            self.mean = mean_tr
            self.std = std_tr

        # Shuffle data
        self.indices = np.arange(len(x))
        if self.shuffle: 
            np.random.shuffle(self.indices)

        self.on_epoch_end()

    def on_epoch_end(self):
        """
        Reshuffle when epoch ends 
        """
        if self.shuffle: 
            np.random.shuffle(self.indices)


    def generate(self, indices_tmp):
        """
        Generate new mini-batch
        """
        mb_max_len = min(max(list(map(len,[self.x[ind] for ind in indices_tmp]))), 30000)
#         mb_max_len = max(list(map(len,[self.x[ind] for ind in indices_tmp])))
        x_mb = np.zeros((self.batch_size, mb_max_len, self.n_feat))
        y_mb = np.zeros((self.batch_size, 1))

        for i, idx in enumerate(indices_tmp):
            if self.x[idx].shape[0]<=mb_max_len:
                x_mb[i, 0:self.x[idx].shape[0]] = (self.x[idx] - self.mean) / self.std
            else:
                #cut chunk
                start_pos = np.random.randint(self.x[idx].shape[0]-mb_max_len+1)
                x_mb[i, :] = (self.x[idx][start_pos:start_pos+mb_max_len,:] - self.mean) / self.std
            y_mb[i] = self.y[idx]

        return x_mb, y_mb

    def __len__(self):
        return int(np.floor(len(self.indices) / self.batch_size))

    def __getitem__(self, index):
        """
        Get new mb
        """
        indices_tmp = \
          self.indices[self.batch_size * index : self.batch_size * (index + 1)]
        x_mb, y_mb = self.generate(indices_tmp)
        return x_mb, y_mb




