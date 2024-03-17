"""Utility functions used in running optimization."""
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

#  dictionary outlining potential seed paths for each of the top 8 seeds
SEED_PATH_DICTIONARY = {
    1: [16, (8, 9), (4, 5, 12, 13), (2, 3, 6, 7, 10, 11, 14, 15)],
    2: [15, (7, 10), (3, 6, 11, 14), (1, 4, 5, 8, 9, 12, 13, 16)],
    3: [14, (6, 11), (2, 7, 10, 15), (1, 4, 5, 8, 9, 12, 13, 16)],
    4: [13, (5, 12), (1, 8, 9, 16), (2, 3, 6, 7, 10, 11, 14, 15)],
    5: [12, (4, 13), (1, 8, 9, 16), (2, 3, 6, 7, 10, 11, 14, 15)],
    6: [11, (3, 14), (2, 7, 10, 15), (1, 4, 5, 8, 9, 12, 13, 16)],
    7: [10, (2, 15), (3, 6, 11, 14), (1, 4, 5, 8, 9, 12, 13, 16)],
    8: [9, (1, 16), (4, 5, 12, 13), (2, 3, 6, 7, 10, 11, 14, 15)],
}
SINGLE_REGION_SEARCH_SPACE = list(np.arange(1, 17))


@dataclass
class RegionBracket:
    seed_path_dictionary: Dict[int, List[Union[int, Tuple[int]]]]
    win_probability_dictionary: Dict[int, Dict[int, float]]

    def __post_init__(self) -> None:
        """Initialize bracket for single region."""
        # dictionary to store the points scored by each seed
        self.points_by_seed = {n + 1: 0 for n in range(16)}
        # the matchup state will change after each potential matchup
        self.current_matchup_state = deepcopy(self.seed_path_dictionary)

    def simulate_region_tournament(self) -> None:
        """Simulate all 4 rouns of the region."""
        for _ in range(4):
            self.simulate_round_and_update_current_state()

    def simulate_round_and_update_current_state(self) -> None:
        """Simulate a single round of the tournament based on the current state."""
        # iterate over the current state and create opponents - the visited data structure
        # will allow us not duplicate simulations in matchups after the first round, where
        # both teams in a matchup will appear in the current state
        updated_matchup_state, visited = {}, set()
        for seed, matchup_path in self.current_matchup_state.items():
            if seed in visited:
                continue
            next_opponent = matchup_path.pop(0)
            if isinstance(next_opponent, tuple):
                # iterate over all elements of tuple until a match is found
                for possible_opponent in next_opponent:
                    if possible_opponent in self.current_matchup_state.keys():
                        current_opponent = possible_opponent
                        # in this case, we need to add the opponent to the visited data structure
                        visited.add(current_opponent)
                        break
            else:
                # this is only the case for the first round of the tourney, no need to do anything here
                current_opponent = next_opponent
            # in this case, we just need to simulate the matchup and record the winner
            win_probability = self.extract_win_probability_by_seed(
                seed,
                current_opponent,
            )
            # draw random binomial sample to simulate game play
            game_outcome = np.random.binomial(n=1, p=win_probability)
            # set which team was the winning seed
            winning_seed = seed if game_outcome else current_opponent
            # update data structures
            self.points_by_seed[winning_seed] += winning_seed
            updated_matchup_state[winning_seed] = matchup_path
        # at the end of our run, we overwrite the current matchup state with the new updated state
        self.current_matchup_state = updated_matchup_state

    def extract_win_probability_by_seed(
        self, current_seed: int, matchup_opponent: int
    ) -> float:
        """Extract the win probability from win probability dictionary."""
        # from the ordering of the seeds, we can't be sure where the win probability is stored in the dictionary
        seed_win_prob_dict = self.win_probability_dictionary.get(current_seed)
        if seed_win_prob_dict:
            matchup_probability = seed_win_prob_dict.get(matchup_opponent)
        # it's possible this is not found, in which case it's in the other dictionary
        if not seed_win_prob_dict or matchup_probability is None:
            # now check the other seed
            seed_win_prob_dict = self.win_probability_dictionary.get(matchup_opponent)
            if not seed_win_prob_dict:
                raise ValueError(
                    f"Matchup probability is missing: {current_seed, matchup_opponent}"
                )
            # in this case, the win probability is 1-the opponent's probability
            matchup_probability = seed_win_prob_dict.get(current_seed)
            if matchup_probability is None:
                raise ValueError(
                    f"Matchup probability is missing: {current_seed, matchup_opponent}"
                )
            matchup_probability = 1.0 - matchup_probability
        return matchup_probability


def clip_continuous_inputs_to_discrete_search_space(
    continuous_input_arr: List[float],
    discrete_search_space: Optional[List[int]],
    replace: bool = False,
) -> List[int]:
    """Clip array of floating point inputs to discrete search space."""
    if discrete_search_space is None:
        discrete_search_space = SINGLE_REGION_SEARCH_SPACE
    output_values = []
    # create array of discrete search space to use in determining position
    search_space_arr = np.array(discrete_search_space)
    # iterate over input
    for value in continuous_input_arr:
        # determine the closest member of the search space
        nearest_neighbor_idx = np.argmin(abs(search_space_arr - value))
        output_values.append(search_space_arr[nearest_neighbor_idx])
        # if replacing is not allowed (i.e. we are only searching in one region where each seed can only exist once)
        # remove the index
        if not replace:
            search_space_arr = np.delete(search_space_arr, nearest_neighbor_idx)
    return output_values
