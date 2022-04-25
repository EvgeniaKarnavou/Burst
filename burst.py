# -*- coding: utf-8 -*-
"""Burst.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1tvbr6XMmF7zNnj5Ot4HfNsbewkX3EQNV
"""

# Commented out IPython magic to ensure Python compatibility.
from torch._C import device
from torchvision.datasets import mnist
import torch
import tensorflow as tf
import matplotlib.pyplot as plt
import numpy as np
import random
import os
import sys
import math 
#!wandb login --relogin
#!pip install wandb --upgrade
#sys.path.insert(0, '/content/drive/MyDrive/Neuro/')
# %cd /content/drive/MyDrive/BurstCNN/
#!pwd
import torchvision
from torchvision import datasets, transforms
import pickle
from abc import ABC, abstractmethod
from enum import Enum, unique
import torch.nn.functional as F
from tqdm import tqdm
!pip install wandb
import wandb
!wandb login

from network import BurstCCN
from optimisers import AdamOptimiser, SynapseLeakOptimiser, SGDOptimiser, SGDMomentumOptimiser, NeuronLeakOptimiser,  NetworkLeakOptimiser, NetworkCostOptimiser, SynapseIntegratorOptimiser, NeuronIntegratorOptimiser, LayerIntegratorOptimiser,  NetworkIntegratorOptimiser, LayerLeakOptimiser 

#directory = '/content/drive/MyDrive/BurstCNN/True-mnist-SGDNetwork-1-0.01'
#torch.manual_seed(1)
#torch.cuda.manual_seed(1)


def downsize():
        mnist_train_data = datasets.MNIST('./datasets/data_mnist', train=True, download=True,
                                        transform=transforms.Compose([
                                            transforms.ToTensor(),
                                            transforms.Normalize((0.1307,), (0.3081,))
                                        ]))

        mnist_test_data = datasets.MNIST('./datasets/data_mnist', train=False,
                                      transform=transforms.Compose([
                                          transforms.ToTensor(),
                                          transforms.Normalize((0.1307,), (0.3081,))
                                      ]))
        
        train_set, validation_set = torch.utils.data.random_split(mnist_train_data, [50000, 10000])
        
        #FULL DATASET
        train_loader = torch.utils.data.DataLoader(train_set, batch_size=32, shuffle=True)
        validation_loader = torch.utils.data.DataLoader(validation_set, batch_size=32, shuffle=True)
        test_loader = torch.utils.data.DataLoader(mnist_test_data, 32, shuffle=True)

        return train_loader, test_loader, validation_loader


class Experiment:
  def __init__(self, train_dataset, test_dataset, validation_dataset):
        self.train_dataset = train_dataset
        self.validation_dataset = validation_dataset
        self.test_dataset = test_dataset
        self.num_epochs = 20
        self.device = torch.device("cpu")
        self.num_seeds = 3
        self.seeds = [1, 55, 1004, 111]
        #self.trained = None

  def intd(self):
      
        p_baseline = 0.5 # Baseline burst probability
        n_hidden_layers = 3
        n_hidden_units = 500 # Number of units in each hidden layer

        Y_learning = False # Whether to learn the feedback Y weights (default=False corresponding to feedback alignment where they are fixed)
        # Y_mode controls how the Y_weights are initialised
        # options are 'tied', 'symmetric_init', random_init'
        # 'random_init': corresponds to the random feedback weights of feedback alignment (default)
        # 'tied': feedback Y weights are kept symmetric with the feedforward weights throughout training
        # 'symmetric_init': feedback Y weights are initialised symmetric with feedforward weights but deviate throughout training
        Y_mode = 'random_init'

        # Y_scale controls the strength of the Y weights and it's interpretation depends on the Y_mode:
        # Y_mode='random_init': the scale is the standard deviation of the normal distribution (mean=0) used for initialisation, pnorm(0) = 0.5
        # Y_mode='symmetric_init' or 'tied': is a controls the ratio of feedforward to feedback weights (Y_scale=1 for exact symmetry)
        Y_scale = 0.5

        Q_learning = True # Whether to learn the feedback Q weights (default=True such that the Q weights learn to cancel the Y weights) 

        # Similar to Y_mode, Q_mode controls how the Q weights are initialised
        # Options are the same as before: 'tied', 'symmetric_init', random_init'
        # 'random_init': corresponds to initially random Q weights that need to align with Y from scratch 
        # 'tied': feedback Q weights are kept symmetric with the feedback Y weights (with a -p_baseline constant ratio i.e. Q = -p_baselineY) such that the two pathways cancel in the absense of an error signal
        # 'symmetric_init': Q weights are initialised symmetric with the feedback Y weights (as for the 'tied' case) but deviate through training (default)
        Q_mode = 'symmetric_init'

        # Q_scale controls the strength of the Q weights and it's interpretation depends on the Q_mode:
        # Q_mode='random_init': the scale is the standard deviation of the normal distribution (mean=0) used for initialisation
        # Q_mode='symmetric_init' or 'tied': is a controls the ratio of Y to Q weights (recommended value of Q_scale=1.0 in this case)
        Q_scale = 1.0

        #working_directory = os.getcwd()
        #self.device = 'cpu'

        #n_epochs = 50
        #self.n_epochs = n_epochs
        batch_size = 32
        self.batch_size = batch_size


        lr = [0.01] * (n_hidden_layers + 1)
        self.lr = lr
        lr_Y = [0.0] * n_hidden_layers + [None]
        self.lr_Y = lr_Y
        lr_Q = [0.000731] * n_hidden_layers + [None]
        self.lr_Q = lr_Q
        momentum = 0.0
        self.momentum = momentum
        weight_decay = 0.0 
        self.weight_decay = weight_decay

        model = BurstCCN(n_inputs=784,
                n_outputs=10,
                p_baseline=p_baseline,
                n_hidden_layers=n_hidden_layers,
                n_hidden_units=n_hidden_units,
                Y_learning=Y_learning,
                Y_mode=Y_mode,
                Y_scale=Y_scale,
                Q_learning=Q_learning,
                Q_mode=Q_mode,
                Q_scale=Q_scale,
                device=self.device)
        self.model = model
        '''if momentum == 0.0:
          optimiser = SGDOptimiser()'''
        #self.optimiser = optimiser
        #beta1=0.9
        #beta2=0.999
        decay_constant = 0.9 #suggested by Hinton
        eps=1e-8
        optimiser = NeuronLeakOptimiser( 
        weight_sizes=[model.classification_layers[i].weight.shape for i in range(len(self.model.classification_layers))],
        bias_sizes=[model.classification_layers[i].bias.shape for i in range(len(self.model.classification_layers))],
        decay_constant = decay_constant,
        eps = eps,
        device=self.device)
        '''optimiser = NetworkIntegratorOptimiser(
             weight_sizes=[model.classification_layers[i].weight.shape for i in range(len(self.model.classification_layers))],
             bias_sizes=[model.classification_layers[i].bias.shape for i in range(len(self.model.classification_layers))],
             eps = eps,
             device = self.device
        )'''
        self.optimiser = optimiser
        #self.run()

  def run(self):
    #wandb.init(project='New' ,name= 'Sgd, r=0.01', entity="evgeniakarnavou")
    for seed in range(self.num_seeds + 1):
      
      torch_seed = self.seeds[seed]
      #random.randint(0, 1000000)
      print(torch_seed)
      torch.manual_seed(torch_seed)
      #torch.manual_seed(1)
      torch.cuda.manual_seed(torch_seed)
      self.intd()
      dic = {"epochs": self.num_epochs, "batch_size": 32, "seed":torch_seed}
      wandb.init(project='NeuronLeaky0.01' ,name= 'r=0.01', config = dic ,entity="evgeniakarnavou")


      test_error, test_loss, test_accuracy = self.test(self.test_dataset)

      best_test_error = test_error
      best_test_error_epoch = 0.0

      
      val_error, val_loss, val_accuracy = self.test(self.validation_dataset)
      

      best_val_error = val_error
      best_val_error_epoch = 0.0


      wandb.log({'test_error': test_error,
                    'test_loss': test_loss,
                    'test_accuracy': test_accuracy,
                    'best_test_error': best_test_error,
                    'best_test_error_epoch': best_test_error_epoch,
                    'val_error': val_error,
                    'val_loss': val_loss,
                    'val_accuracy': val_accuracy,
                    'best_val_error': best_val_error,
                    'best_val_error_epoch': best_val_error_epoch})
      train_losses = []
      epochs = []
      for epoch in range(1, self.num_epochs + 1): 
          print(f"\nEpoch {epoch}.")
        
          train_error, train_loss, train_accuracy = self.train(self.train_dataset)
          #self.model.log_layer_statesJen()
          test_error, test_loss, test_accuracy = self.test(self.test_dataset)
          val_error, val_loss, val_accuracy = self.test(self.validation_dataset)
          
          if math.isnan(test_error):
              break

          if test_error < best_test_error:
              best_test_error = test_error
              best_test_error_epoch = epoch

          
          if val_error < best_val_error:
                  best_val_error = val_error
                  best_val_error_epoch = epoch
          
          wandb.log({'train_error': train_error,
                        'train_accuracy': train_accuracy,
                        'train_loss': train_loss,
                        'test_error': test_error,
                        'test_loss': test_loss,
                        'test_accuracy': test_accuracy,
                        'best_test_error': best_test_error,
                        'best_test_error_epoch': best_test_error_epoch,
                        'val_error': val_error,
                        'val_loss': val_loss,
                        'val_accuracy': val_accuracy,
                        'best_val_error': best_val_error,
                        'best_val_error_epoch': best_val_error_epoch,
                        'epoch': epoch})
                                          

          train_losses.append(train_loss)
          epochs.append(epoch)
          #print(train_losses, len(train_losses))
          
          print(f"Train: {train_error}, Test: {test_error}, T_Acc: {train_accuracy}, Test_Acc: {test_accuracy}")
      
      #with open((directory), 'wb') as handle:  #'wb' = write binary
          #pickle.dump(self.model, handle, protocol=pickle.HIGHEST_PROTOCOL)
      #torch.save(self.model.state_dict(), directory)

    '''trained_model = model = BurstCCN(n_inputs=784,
                n_outputs=10,
                p_baseline=0.5,
                n_hidden_layers=3,
                n_hidden_units=500,
                Y_learning=False,
                Y_mode='random_init',
                Y_scale=0.5,
                Q_learning=True,
                Q_mode='symmetric_init',
                Q_scale=1,
                device=torch.device("cpu"))'''
    #trained_model.load_state_dict(torch.load(directory))
    #trained = pickle.load(open(directory, 'rb'))
    #self.trained = trained
    #test_error, test_loss, activations = self.test2(self.test_dataset)
    #print(test_error, test_loss)
    


  def train(self, data_loader):
        self.model.train()
        
        train_loss = 0.0
        correct = 0
        total = 0
        #t_loss = []
        progress_bar = tqdm(data_loader)
       
        for batch_index, (inputs, targets) in enumerate(progress_bar):
            
            inputs, targets = inputs.to(self.model.device), targets.to(self.model.device)
            t = F.one_hot(targets, num_classes=10).float()
            

            outputs = self.model(inputs) #32 arrays(oso batches dld) pou exoun mesa 10 times(osa classes) apo 0 mexri 1
            #print(outputs), #kanei to forward pass gia ka8e layer 

            loss = self.model.loss(outputs, t) 

            #print(self.model.classification_layers[0]) #prints this: BurstCCNOutputLayer(in_features=500, out_features=10, bias=True)

            self.model.backward(t) 
            
            #apic = []
            #for i in range(1, len(self.model.classification_layers) - 1):
              #layer = self.model.classification_layers[i]
              #apic.append(layer.apic.flatten().cpu().numpy())
            
            
            self.model.update_weights(lrs=self.lr, lrs_Y=self.lr_Y, lrs_Q=self.lr_Q, optimiser=self.optimiser, global_cost=loss.item(),
                                      momentum=self.momentum, weight_decay=self.weight_decay)
            
            train_loss += loss
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()

            progress_bar.set_description("Train Loss: {:.3f} | Acc: {:.3f}% ({:d}/{:d})".format(train_loss / (batch_index + 1), 100 * correct / total, correct, total))
            #t_loss.append((train_loss / (batch_index + 1)))
        #self.model.log_layer_stateJen()
        return 100.0 * (1.0 - correct / total), train_loss / (batch_index + 1), 100.0 * correct / total


  def test(self, data_loader):
    self.model.eval()

    test_loss = 0.0
    correct = 0
    total = 0
    with torch.no_grad():
        progress_bar = tqdm(data_loader)
        for batch_idx, (inputs, targets) in enumerate(progress_bar):
            inputs, targets = inputs.to(self.model.device), targets.to(self.model.device)

            t = F.one_hot(targets, num_classes=10).float() #tensors mexri 10 pou ola einai 0 ektos apo 1 pou 8a einai 1, to corresponding target noumero

            outputs = self.model(inputs) 

            loss = self.model.loss(outputs, t)

            test_loss += loss.item()

            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()

            progress_bar.set_description("Test Loss: {:.3f} | Acc: {:.3f}% ({:d}/{:d})".format(test_loss / (batch_idx + 1), 100 * correct / total, correct, total))

    return 100 * (1.0 - correct / total), test_loss / (batch_idx + 1), 100.0 * correct / total



def main():
  train, test, validation = downsize()
  experiment = Experiment(train, test, validation)
  #experiment.intd()
  experiment.run()
  
  #experiment.run()




main()