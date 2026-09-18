# Mathematical Model: Sigmoid Priority, Directed Weights, and Operational Loss

This note separates three ideas that are easy to conflate in this repository:

1. the **historical pair-weight sigmoid** used by the original demo,
2. the **current node-priority sigmoid** used to map order features into a bounded priority, and
3. the **operational objective** that evaluates a complete delivery permutation.

## 1. Current order-priority score

For order \(j\),

$$
\begin{aligned}
z_j =\;& b
+a_I\frac{I_j}{10}
+a_W\min\left(\frac{E_j}{\tau_j},3\right)
+a_RR_j \\
&+a_D\min\left(\frac{d_{0j}}{50},3\right)
+a_V\left(1-\frac{\min(v_j,v_0)}{v_0}\right).
\end{aligned}
$$

The sigmoid maps this unbounded score into \((0,1)\):

$$
s_j=\sigma(z_j)=\frac{1}{1+e^{-z_j}}.
$$

The scheduler rescales it to a bounded priority:

$$
\omega_j = 1+9s_j = 1+9\sigma(z_j), \qquad 1<\omega_j<10.
$$

This is implemented by `weights()` in `scheduler/core.py`.

## 2. Directed matrix notation: \(w_{ij}\) and \(w_{ji}\)

The UI weight matrix is a destination-priority lookup:

$$
w_{ij}=\omega_j, \qquad i\ne j.
$$

Therefore

$$
w_{ji}=\omega_i,
$$

and generally

$$
w_{ij}\ne w_{ji}.
$$

This is intentional: direction means “priority of the destination I am about to serve”.

By contrast,

$$
D_{ij}=D_{ji},
$$

while travel time can be directional,

$$
T_{ij}\ne T_{ji},
$$

because the implementation applies destination-local speed limits near the destination node.

For the historical/disclosure pair interaction, a symmetric coupling is

$$
q_{ij}=1+\omega_i+\omega_j=q_{ji}.
$$

## 3. Route arrival recursion

For chromosome

$$
\pi=(\pi_1,\ldots,\pi_N),
$$

the first arrival is

$$
A_{\pi_1}=T_{0,\pi_1}.
$$

For later stops,

$$
A_{\pi_k}
=A_{\pi_{k-1}}
+S_{\pi_{k-1}}
+T_{\pi_{k-1},\pi_k},
\qquad k\ge2,
$$

where \(S_j\) is service time.

## 4. Current operational objective

The default objective is

$$
L(\pi)=T_{finish}
+\lambda\frac{\sum_j\omega_jA_j}{\sum_j\omega_j}
+\mu\sum_jR_j\frac{\max(0,E_j+A_j-\tau_j)}{\tau_j}
+\nu D_{total}.
$$

The four terms are completion time, priority-weighted arrival time, lateness/risk penalty, and geometric distance.

Defaults are \(\lambda=1\), \(\mu=120\,s\), and \(\nu=1\,s/m\).

## 5. Exact propagation from \(z_j\) into the route loss

Substituting

$$
\omega_j=1+9\sigma(z_j)
$$

gives

$$
L_{priority}(\pi)
=\lambda
\frac{\sum_j[1+9\sigma(z_j)]A_j}
{\sum_j[1+9\sigma(z_j)]}.
$$

So the chain is

$$
z_j
\rightarrow \sigma(z_j)
\rightarrow \omega_j
\rightarrow L_{priority}(\pi)
\rightarrow \text{GA ranking of permutations}.
$$

The GA is discrete and does **not** use gradients, but the derivative helps explain sensitivity:

$$
\frac{d\omega_j}{dz_j}
=9\sigma(z_j)[1-\sigma(z_j)].
$$

Let

$$
\bar A_\omega
=\frac{\sum_k\omega_kA_k}{\sum_k\omega_k}.
$$

For a fixed route,

$$
\frac{\partial \bar A_\omega}{\partial z_j}
=
\frac{9\sigma(z_j)[1-\sigma(z_j)]}{\sum_k\omega_k}
(A_j-\bar A_\omega).
$$

Therefore sensitivity is greatest near \(z_j=0\), saturates for large \(|z_j|\), and is strongest when order \(j\)'s arrival time differs strongly from the current weighted mean. Changing the weights can still change the winning chromosome, so this derivative is local fixed-route sensitivity rather than the full discrete GA response.

## 6. Historical sigmoid formula from the original demo

The original `project_demo(GA_and_APF_routing)/util/TSP_GA.py` computes

$$
x=\frac{d_{ij}}
{10\left[1+\sigma((\omega_i+\omega_j)/5)\right]},
$$

then divides by the 1-based visit position \(k\):

$$
C^{old}_{ij,k}
=\frac{d_{ij}}
{10k\left[1+\sigma((\omega_i+\omega_j)/5)\right]}.
$$

So the original sigmoid modifies an edge-distance denominator using a pair of endpoint weights.

## 7. Disclosure-comparison mode in the current engine

The current engine also keeps a comparison mode:

$$
C^{disc}_{ij,k}
=\sigma\left(
\frac{d_{ij}}
{10k(1+\omega_i+\omega_j)}
\right).
$$

The route score is the sum of these edge terms.

This is not the default operational objective because route geometry, order priority, lateness, and business risk are easier to inspect and tune when they remain separate terms.
