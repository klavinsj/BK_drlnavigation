from ..common.settings import REWARD_FUNCTION, COLLISION_OBSTACLE, COLLISION_WALL, TUMBLE, SUCCESS, TIMEOUT, RESULTS_NUM

goal_dist_initial = 0

reward_function_internal = None

def get_reward(succeed, action_linear, action_angular, distance_to_goal, goal_angle, min_obstacle_distance):
    return reward_function_internal(succeed, action_linear, action_angular, distance_to_goal, goal_angle, min_obstacle_distance)

def get_reward_A(succeed, action_linear, action_angular, goal_dist, goal_angle, min_obstacle_dist):
        # [-3.14, 0]
        r_yaw = -1 * abs(goal_angle)

        # [-4, 0]
        r_vangular = -1 * (action_angular**2)

        # [-1, 1]
        r_distance = (2 * goal_dist_initial) / (goal_dist_initial + goal_dist) - 1

        # [-20, 0]
        if min_obstacle_dist < 0.22:
            r_obstacle = -20
        else:
            r_obstacle = 0

        # [-2 * (2.2^2), 0]
        r_vlinear = -1 * (((0.22 - action_linear) * 10) ** 2)
        #if goal_dist < 0.4:
        #    r_vlinear = -4.0 * abs(action_linear) * (0.4 - goal_dist) / 0.4
        #else:
        #    r_vlinear = -1 * (((0.22 - action_linear) * 10) ** 2)

        reward = r_yaw + r_distance + r_obstacle + r_vlinear + r_vangular - 1

        if succeed == SUCCESS:
            reward += 2500
        elif succeed == COLLISION_OBSTACLE or succeed == COLLISION_WALL:
            reward -= 2000
        return float(reward)

# Define your own reward function by defining a new function: 'get_reward_X'
# Replace X with your reward function name and configure it in settings.py
def get_reward_B(succeed, action_linear, action_angular, goal_dist, goal_angle, min_obstacle_dist):
    global goal_dist_initial
    if goal_dist_initial == 0:
        goal_dist_initial = goal_dist        # first step after reset
    progress     = goal_dist_initial - goal_dist
    goal_dist_initial = goal_dist            # store for next call
    r_progress   = 4.0 * progress            # +4 reward per metre

    # ---------- speed & spin penalties --------------------------- #
    speed_norm   = abs(action_linear)        # 0…1
    r_speed      = -0.05 * (1.0 - speed_norm)

    r_spin       = -0.02 * abs(action_angular)

    # ---------- obstacle proximity penalty ----------------------- #
    r_obstacle   = -10.0 if min_obstacle_dist < 0.22 else 0.0

    # ---------- terminal bonuses / penalties --------------------- #
    r_terminal   = 0.0
    if succeed == SUCCESS:
        r_terminal = +20.0
    elif succeed in (COLLISION_OBSTACLE, COLLISION_WALL, TUMBLE):
        r_terminal = -25.0

    # ---------- total reward ------------------------------------- #
    reward = r_progress + r_speed + r_spin + r_obstacle + r_terminal
    return float(reward)

def reward_initalize(init_distance_to_goal):
    global goal_dist_initial
    goal_dist_initial = init_distance_to_goal

function_name = "get_reward_" + REWARD_FUNCTION
reward_function_internal = globals()[function_name]
if reward_function_internal == None:
    quit(f"Error: reward function {function_name} does not exist")
