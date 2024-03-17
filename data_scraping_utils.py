"""Utility functions used to scrape head to head historical seed matchup data."""
import re
import requests
from itertools import chain
from typing import Dict, List

import bs4
from bs4 import BeautifulSoup


NCAA_WIKI_URL = (
    "https://en.wikipedia.org/wiki/NCAA_Division_I_men%27s_basketball_tournament"
)


def scrape_winning_percentage_dict_from_wikipedia() -> Dict[int, Dict[int, float]]:
    """Scrape single region head to head win probability for NCAA March Madness from wikipedia."""
    page_data = requests.get(NCAA_WIKI_URL)
    page_soup = BeautifulSoup(page_data.content, "html.parser")
    # start by creating our base object and parse the round of 64 results, which appear in a different
    # format than the rest of the results
    base_winning_percentage_dict = parse_round_of_64_results(page_soup=page_soup)
    # now identify all of the head to head seeding tables
    all_seed_tables = identify_head_to_head_seed_tables(page_soup=page_soup)
    # iterate over all tables and update winning percentage dictionary
    for seed_table in all_seed_tables:
        seed_win_pctage_dict = parse_wikipedia_bracket_matchup_table(
            table_element=seed_table,
        )
        # there could be multiple seeds in each dictionary
        for seed, prob_dict in seed_win_pctage_dict.items():
            if seed in base_winning_percentage_dict.keys():
                base_winning_percentage_dict[seed].update(prob_dict)
            else:
                base_winning_percentage_dict[seed] = prob_dict
    return base_winning_percentage_dict


def identify_head_to_head_seed_tables(
    page_soup: bs4.BeautifulSoup,
) -> List[bs4.element.Tag]:
    """Load page data and identify all head to head seed tables by html tags."""
    # identify all tables on page
    all_tables = page_soup.find_all("table", {"class": "wikitable"})
    # the tables we're looking for have a specific style, so we can identify using this tag
    head_to_head_seed_tables = [
        table for table in all_tables if table.find("td", {"class": "table-rh"})
    ]
    return head_to_head_seed_tables


def parse_round_of_64_results(
    page_soup: bs4.BeautifulSoup,
) -> Dict[int, Dict[int, float]]:
    """
    Parse Round of 64 results and return dictionary of winning percentages.

    This is a hacky approach - unlike the other round results which have an identifiable html tag,
    this is a group of lines without an identifier. The match will be made by iterating over text content
    of all lines and extracting the match group we need.

    Parameters
    ----------
    page_soup : bs4.BeautifulSoup
        searchable soup object

    Returns
    -------
    Dict[int, Dict[int, float]]
        dictionary keyed by integer seed value containing integer seed of opponent and the corresponding
        win percentage

    """
    # find all groups of line items
    all_ul = page_soup.find_all("ul")
    # iterate over this group and check the line items until we find our match group
    for ul in all_ul:
        all_lines = ul.find_all("li")
        if all_lines:
            first_line = all_lines[0].contents[0]
            if isinstance(first_line, str):
                # if it's a string, we can check for our match group
                if re.match(r"The\sNo\.", first_line):
                    seeding_lines = all_lines
                    break
    # now we can parse the results easily
    base_winning_percentage_dict = {}
    for line_item in seeding_lines:
        line_contents = line_item.contents[0]
        # there's a two step regex here since there are other potential number match groups
        # in the sentence text we need to avoid
        seed_1, seed_2 = [
            int(re.search("\d+", match).group())
            for match in re.findall(r"No\.\s\d{1,2}", line_contents)
        ]
        # now get the winning percentage
        winning_percentage = float(re.search(r"\.\d+", line_contents).group())
        base_winning_percentage_dict[seed_1] = {seed_2: winning_percentage}
    return base_winning_percentage_dict


def parse_wikipedia_bracket_matchup_table(
    table_element: bs4.element.Tag,
) -> Dict[int, Dict[int, float]]:
    """
    Parse wikipedia table containing historical bracket matchup percentages from BeautifulSoup output.

    Parameters
    ----------
    table_element : bs4.element.Tag
        all html elements within table tag in html response from wikipedia page

    Returns
    -------
    Dict[int, Dict[int, float]]
        dictionary keyed by integer seed value containing integer seed of opponent and the corresponding
        win percentage

    """
    # find all rows in table element
    all_table_rows = table_element.find_all("tr")
    # the first row contains the opponent seeds
    header_row = all_table_rows[0]
    # the first row is the header row, the last row is the "Totals" row, so the percentages themselves are in the
    # middle N rows
    content_rows = all_table_rows[1:-1]
    # identify the header seeds
    header_seeds = re.findall(
        "\d{1,2}",
        "_".join(
            chain.from_iterable(
                [header.contents for header in header_row.find_all("th")[1:-1]]
            )
        ),
    )
    # convert to integer type, it'll work smoother in the optimization algorithm
    header_seeds = [int(seed) for seed in header_seeds]
    # create dictionary to store winning percentages
    winning_percentage_dict = {}
    # iterate over all rows with content
    for row in content_rows:
        # identify the seed within each row
        seed = int(re.search("\d{1,2}", row.find("th").contents[0]).group())
        # extract the winning percentage between this seed combination
        all_tags = [
            re.search("\d*\.\d+", s)
            for s in (
                chain.from_iterable([tag.contents for tag in row.find_all("td")][:-1])
            )
        ]
        # it's possible that two seed combinations have never played, but the optimization will probably
        # encounter these, so in these cases we'll assign an arbitrary value of 0.50 since there's no way
        # of knowing what the actual historical win percentage would be - these are very low probability
        # so we'll work them out with repeated sampling
        winning_percentages = [
            float(match.group()) if match else 0.50 for match in all_tags
        ]
        # add the associated winning percentage between this seed combination
        winning_percentage_dict[seed] = {
            other_seed: pctage
            for other_seed, pctage in zip(header_seeds, winning_percentages)
        }
    return winning_percentage_dict
