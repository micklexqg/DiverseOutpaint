# Import Packages
import warnings
warnings.filterwarnings("ignore")
import os
import torch
from torch import nn, optim
from torch.utils import data
from torch.nn import functional as F
from data_utils import *
from model_utils import Decoder, Encoder
from data_utils import SyntheticDataset
import matplotlib.pyplot as plt
from skimage.io import imsave
from sklearn.metrics import mean_squared_error
from sklearn.metrics.pairwise import manhattan_distances
import numpy as np
import pdb
from scipy import linalg

def calculate_frechet_distance(mu1, sigma1, mu2, sigma2, eps=1e-6):
    """Numpy implementation of the Frechet Distance.
    The Frechet distance between two multivariate Gaussians X_1 ~ N(mu_1, C_1)
    and X_2 ~ N(mu_2, C_2) is
            d^2 = ||mu_1 - mu_2||^2 + Tr(C_1 + C_2 - 2*sqrt(C_1*C_2)).
    Stable version by Dougal J. Sutherland.
    Params:
    -- mu1   : Numpy array containing the activations of a layer of the
               inception net (like returned by the function 'get_predictions')
               for generated samples.
    -- mu2   : The sample mean over activations, precalculated on an
               representative data set.
    -- sigma1: The covariance matrix over activations for generated samples.
    -- sigma2: The covariance matrix over activations, precalculated on an
               representative data set.
    Returns:
    --   : The Frechet Distance.
    """

    mu1 = np.atleast_1d(mu1)
    mu2 = np.atleast_1d(mu2)

    sigma1 = np.atleast_2d(sigma1)
    sigma2 = np.atleast_2d(sigma2)

    assert mu1.shape == mu2.shape, \
        'Training and test mean vectors have different lengths'
    assert sigma1.shape == sigma2.shape, \
        'Training and test covariances have different dimensions'

    diff = mu1 - mu2

    # Product might be almost singular
    covmean, _ = linalg.sqrtm(sigma1.dot(sigma2), disp=False)
    if not np.isfinite(covmean).all():
        msg = ('fid calculation produces singular product; '
               'adding %s to diagonal of cov estimates') % eps
        print(msg)
        offset = np.eye(sigma1.shape[0]) * eps
        covmean = linalg.sqrtm((sigma1 + offset).dot(sigma2 + offset))

    # Numerical error might give slight imaginary component
    if np.iscomplexobj(covmean):
        if not np.allclose(np.diagonal(covmean).imag, 0, atol=1e-3):
            m = np.max(np.abs(covmean.imag))
            raise ValueError('Imaginary component {}'.format(m))
        covmean = covmean.real

    tr_covmean = np.trace(covmean)

    return (diff.dot(diff) + np.trace(sigma1) +
            np.trace(sigma2) - 2 * tr_covmean)
    
    
# noise sampling 
def noise_sampling(batch_size, num_sample, noise_dim):
	noise = torch.FloatTensor(batch_size, num_sample, noise_dim).uniform_()
	return noise

# Configurations and Hyperparameters
gpu_id = 3
lr_rate = 2e-4
num_epochs = 101
num_sample = 10
noise_dim = 2

# Random Initialization
torch.manual_seed(1)
np.random.seed(1)

# Dataloader
action_dir = '../data/test_input.npy'
state_dir = '../data/test_output.npy'
dataset = SyntheticDataset(action_dir, state_dir)
loader = data.DataLoader(dataset, batch_size=1)

# Models
encoder = torch.load('models/encoder.pt')
decoder = torch.load('models/decoder.pt')


# Inference and draw the datapoints
n_samples = len(loader)
recon_err_arr = np.zeros((n_samples))
local_div_score_arr = np.zeros((n_samples))
overall_y_hat_sample = np.zeros((n_samples*10,2)); s = 0

y_arr = np.zeros((n_samples, 2)); y_hat_arr = np.zeros((10, n_samples, 2))

for i, inputs in enumerate(loader):
    x, y = inputs

    y_arr[i] = y.data.numpy()[0]

    ########## Encode #########
    x_unsqueeze = (x[:,None,:]).expand(-1,num_sample,-1)
    x_unsqueeze = x_unsqueeze.contiguous().view(-1,x_unsqueeze.shape[2])
    z = encoder(x_unsqueeze)
    
    ########## Diverse Sampling in Uniform Space ########
    batch_size = x.shape[0]
    noise = noise_sampling(batch_size, num_sample, noise_dim)
    
    ########## Decode ########
    z_c_concat = torch.cat([z, noise.view(-1, noise.size(2))], dim=1)
    y_hat_all = decoder(z_c_concat)  
    
    y_hat_sample = np.zeros((10,2))
    for j in range(10):
        y_hat = y_hat_all.data.numpy()[j]
        y_hat_sample[j] = y_hat
        
        overall_y_hat_sample[s] = y_hat
        s += 1
    
        y_hat_arr[j, i] = y_hat
    
    y_hat_avg = np.average(y_hat_sample, axis=0)
    recon_err_arr[i] = mean_squared_error(y.data.numpy()[0], y_hat_avg)
#    recon_err_arr[i] = manhattan_distances(np.expand_dims(y.data.numpy()[0], 0),np.expand_dims(y_hat_avg,0))
    
    # local diversity score
    local_div_score = 0
    for m in range(10):
        for n in range(10):
            local_div_score += manhattan_distances(np.expand_dims(y_hat_sample[m], 0),np.expand_dims(y_hat_sample[n],0))
    local_div_score /= 100
    local_div_score_arr[i] = local_div_score


mu1 = np.mean(y_arr, axis=0); sigma1 = np.cov(y_arr, rowvar=False)
FD = 0
for i in range(10):
    mu2 = np.mean(y_hat_arr[i], axis=0); sigma2 = np.cov(y_hat_arr[i], rowvar=False)
    FD += calculate_frechet_distance(mu1, sigma1, mu2, sigma2, eps=1e-6)
FD /= 10
print('FD: ', FD)

print('recon error: ', np.average(recon_err_arr))
print('local div score: ', np.average(local_div_score_arr))


        
