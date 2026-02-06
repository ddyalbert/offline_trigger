import numpy as np
import math
from typing import Optional
 

class EMPCA:
    """
    X: 每一列代表一个观察样本 (n_var, n_obs)
    var_weight: (n_var,)   w_d = 1 / sigma_d^2
    obs_weight: (n_obs,)
    """
    X: Optional[np.ndarray] = None
    comps: np.ndarray
    
    n_comp: int
    n_obs: int
    n_var: int

    _temp_list: list[np.ndarray] = []

    def __init__(self, wen_len, max_iter=500, tol=1e-6):
        self.win_len = wen_len
        self.max_iter = max_iter
        self.tol = tol

    def set_weights(self, 
                var_weight: Optional[np.ndarray] = None, 
                obs_weight: Optional[np.ndarray] = None):

        if var_weight is None:
            var_weight = np.ones(self.n_var)
        elif len(var_weight) != self.n_var:
            raise ValueError("length of var_weight must be n_var!")
            
        if obs_weight is None:
            obs_weight = np.ones(self.n_obs)
        elif len(obs_weight) != self.n_obs:
            raise ValueError("length of obs_weight must be n_obs!")

        self.var_weight = var_weight
        self.obs_weight = obs_weight
    
    def add_data(self, v: np.ndarray):
        """
        v: 一个观察样本 (n_var,)
        """
        vf = np.fft.rfft(v)
        self._temp_list.append(vf[1:,None])
        
    def get_data(self, X: np.ndarray = None):
        if X is None:
            X =np.hstack(self._temp_list)
            self._temp_list = []
        
        self.n_var, self.n_obs = X.shape
        self.X = X


    def fit(self, n_comp: int = 1):
        
        rng = np.random.default_rng(0)
        P = rng.normal(size=(self.n_var, n_comp)) + 1j * rng.normal(size=(self.n_var, n_comp))

        prev_loss = 0

        for j in range(self.max_iter):
            """
            X: (n_var, n_obs)
            P: (n_var, n_comp)
            C: (n_comp, n_obs)
            """
            
            # ===== E step =====
            ww = P.conj().T * self.var_weight      # (n_comp, n_var)
            C = np.linalg.solve(ww @ P, ww @ self.X)
            # ===== M step =====
            ww = (C * self.obs_weight).conj().T    # (n_obs, n_comp)
            P = np.linalg.solve(C @ ww, (self.X @ ww).conj().T).conj().T

            # ---------- loss convergence ----------
            loss = 0.0
            for i in range(self.n_obs):
                diff_i = (self.X[:, i] - P @ C[:, i]).T
                loss += np.sum(abs(diff_i)**2 * self.var_weight) * self.obs_weight[i]
            tol = loss
            if tol < self.tol:
                print(f"Iteration finished: tolerance {tol:g}, {j + 1}-th time")
                break
            prev_loss = loss
            
        if j == self.max_iter - 1:
            print(f"Warning: max_iter {self.max_iter} reached, tolerance {tol:g}")


        self.n_comp = n_comp
        self.coff  = C
        self.comps = P

    def _get_comp(self) -> list[np.ndarray]:

        comps = []
        for i in range(self.n_comp):
            comp = np.append(0, self.comps[:,i])
            comp = comp / comp[-1]
            comp = np.fft.irfft(comp)
            comp = comp - comp[0]
            ind = np.argmax(abs(comp))
            comp = comp / comp[ind]
            # print(comp)
            comps.append(comp)
        return comps