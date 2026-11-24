from enum import Enum


class SortOption(str, Enum):
    RELEVANCE = "relevance"
    YEAR_NEWEST = "year_desc"
    YEAR_OLDEST = "year_asc"
    TITLE_AZ = "title_asc"
    TITLE_ZA = "title_desc"


RELEVANCE_SORT = [{"_score": "desc"}, {"dct_title_s.keyword": "asc"}, {"id": "asc"}]

SORT_MAPPINGS = {
    SortOption.RELEVANCE: RELEVANCE_SORT,
    SortOption.YEAR_NEWEST: [{"gbl_indexYear_im": "desc"}, {"_score": "desc"}],
    SortOption.YEAR_OLDEST: [{"gbl_indexYear_im": "asc"}, {"_score": "desc"}],
    SortOption.TITLE_AZ: [{"dct_title_s.keyword": "asc"}, {"_score": "desc"}],
    SortOption.TITLE_ZA: [{"dct_title_s.keyword": "desc"}, {"_score": "desc"}],
}
