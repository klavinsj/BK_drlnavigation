import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .off_policy_agent import OffPolicyAgent, Network
from .td3 import Critic   # twin-Q critic network

class ActorSAC(Network):
    def __init__(self, name, state_size, action_size, hidden_size):
        super().__init__(name)
        self.fc1     = nn.Linear(state_size, hidden_size)
        self.fc2     = nn.Linear(hidden_size, hidden_size)
        self.mean    = nn.Linear(hidden_size, action_size)
        self.log_std = nn.Linear(hidden_size, action_size)
        for l in (self.fc1, self.fc2, self.mean, self.log_std):
            nn.init.xavier_uniform_(l.weight)
            l.bias.data.fill_(0.01)

    def forward(self, s):
        x1 = F.relu(self.fc1(s))
        x2 = F.relu(self.fc2(x1))
        μ  = self.mean(x2)
        logσ = torch.clamp(self.log_std(x2), -20, 2)
        return x1, x2, μ, logσ

    def sample(self, s):
        x1, x2, μ, logσ = self.forward(s)
        σ    = logσ.exp()
        dist = torch.distributions.Normal(μ, σ)
        x_t  = dist.rsample()
        a    = torch.tanh(x_t)
        logπ = (dist.log_prob(x_t)
               - torch.log(1 - a.pow(2) + 1e-6)
               ).sum(-1, keepdim=True)
        return x1, x2, a, logπ

class SAC(OffPolicyAgent):
    def __init__(self, device, simulation_speed):
        super().__init__(device, simulation_speed)

        # networks
        self.actor         = self.create_network(ActorSAC, 'actor')
        self.critic        = self.create_network(Critic,  'critic')
        self.critic_target = self.create_network(Critic,  'target_critic')
        self.hard_update(self.critic_target, self.critic)

        # optimizers
        self.actor_optimizer  = self.create_optimizer(self.actor)
        self.critic_optimizer = self.create_optimizer(self.critic)

        # entropy coeff
        self.target_entropy  = -float(self.action_size)
        self.log_alpha       = torch.zeros(1, requires_grad=True, device=self.device)
        self.alpha_optimizer = torch.optim.Adam([self.log_alpha], lr=self.learning_rate)

    def attach_visual(self, visual):
        # called by DrlAgent
        self.visual         = visual
        self.actor.visual   = visual

    def get_action(self, state, is_training, step, visualize=False):
        s = torch.from_numpy(np.asarray(state, np.float32)) \
                 .to(self.device).unsqueeze(0)

        if is_training:
            x1, x2, a, logπ = self.actor.sample(s)
        else:
            # deterministic: use mean
            x1, x2, μ, logσ = self.actor.forward(s)
            a = torch.tanh(μ)

        # visualise if requested
        if visualize and hasattr(self, 'visual') and self.visual:
            # TD3 style visual:  state, action, hidden-layers, biases
            self.visual.update_layers(s,
                                      a.squeeze(0),
                                      [x1, x2],
                                      [self.actor.fc1.bias, self.actor.fc2.bias])

        a_np = a.squeeze(0).detach().cpu().numpy()
        a_np[0] = np.clip(a_np[0], -1.0, 1.0)
        a_np[1] = np.clip(a_np[1], -1.0, 1.0)
        return a_np.tolist()

    def get_action_random(self):
        return list(np.random.uniform(-1.0, 1.0, self.action_size))

    def train(self, state, action, reward, next_state, done):
        # critic update
        with torch.no_grad():
            _, _, a2, logπ2 = self.actor.sample(next_state)
            q1_t, q2_t      = self.critic_target(next_state, a2)
            q_target        = torch.min(q1_t, q2_t) - self.log_alpha.exp() * logπ2
            y               = reward + (1 - done) * self.discount_factor * q_target

        q1, q2 = self.critic(state, action)
        loss_c = F.smooth_l1_loss(q1, y) + F.smooth_l1_loss(q2, y)
        self.critic_optimizer.zero_grad()
        loss_c.backward()
        nn.utils.clip_grad_norm_(self.critic.parameters(), 2.0)
        self.critic_optimizer.step()

        # actor update
        _, _, a_pi, logπ = self.actor.sample(state)
        q1_pi, q2_pi     = self.critic(state, a_pi)
        loss_a = (self.log_alpha.exp() * logπ - torch.min(q1_pi, q2_pi)).mean()
        self.actor_optimizer.zero_grad()
        loss_a.backward()
        nn.utils.clip_grad_norm_(self.actor.parameters(), 2.0)
        self.actor_optimizer.step()

        # temperature update
        loss_α = -(self.log_alpha * (logπ + self.target_entropy).detach()).mean()
        self.alpha_optimizer.zero_grad()
        loss_α.backward()
        self.alpha_optimizer.step()

        # soft‐update
        self.soft_update(self.critic_target, self.critic, self.tau)

        return [loss_c.detach().cpu(), loss_a.detach().cpu()]
